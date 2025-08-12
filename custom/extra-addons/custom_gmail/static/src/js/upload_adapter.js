/** @odoo-module **/

function resizeImage(file, maxSize = 800, quality = 0.7) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                // Xác định tỉ lệ scale
                let width = img.width;
                let height = img.height;

                if (width > height) {
                    if (width > maxSize) {
                        height = Math.round(height * (maxSize / width));
                        width = maxSize;
                    }
                } else {
                    if (height > maxSize) {
                        width = Math.round(width * (maxSize / height));
                        height = maxSize;
                    }
                }

                // Tạo canvas
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;

                // Vẽ ảnh vào canvas (đã resize)
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Xuất canvas -> Blob (định dạng JPEG)
                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            resolve(blob);
                        } else {
                            reject(new Error("Canvas is empty"));
                        }
                    },
                    'image/jpeg',
                    quality
                );
            };

            img.onerror = (err) => reject(err);
            img.src = event.target.result;
        };

        reader.onerror = (err) => reject(err);
        reader.readAsDataURL(file);
    });
}


export default class UploadImageAdapter {
    constructor(loader) {
        this.loader = loader;
    }

    upload() {
        // Lấy file gốc do CKEditor cung cấp
        return this.loader.file
            .then(file => {
                // 1) Resize/Compress ảnh trước
                return resizeImage(file, 800, 0.7);
            })
            .then(resizedBlob => {
                // 2) Upload ảnh đã thu nhỏ lên Odoo
                const formData = new FormData();
                // Đặt tên file gốc, hoặc có thể thay đổi
                formData.append('upload', resizedBlob, 'resized_' + Date.now() + '.jpg');

                return fetch('/custom_gmail/upload_image', {
                    method: 'POST',
                    body: formData,
                    credentials: 'include',
                });
            })
            .then(res => res.json())
            .then(json => {
                // CKEditor muốn object: { default: <image url> }
                return { default: json.url };
            });
    }

    abort() {
        // No-op
    }
}
