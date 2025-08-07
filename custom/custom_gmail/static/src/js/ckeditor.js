/** @odoo-module **/

import UploadImageAdapter from './upload_adapter';

function MyCustomUploadPlugin(editor) {
    editor.plugins.get('FileRepository').createUploadAdapter = (loader) => {
        return new UploadImageAdapter(loader);
    };
}

export function loadCKEditor() {
    return new Promise((resolve, reject) => {
        if (!document.getElementById("ckeditor_script")) {
            const script = document.createElement("script");
            script.id = "ckeditor_script";
            script.src = "https://cdn.ckeditor.com/ckeditor5/39.0.0/classic/ckeditor.js";
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Failed to load CKEditor"));
            document.head.appendChild(script);
        } else if (window.ClassicEditor) {
            resolve();
        } else {
            const existingScript = document.getElementById("ckeditor_script");
            existingScript.onload = () => resolve();
            existingScript.onerror = () => reject(new Error("Failed to load CKEditor"));
        }
    });
}

export async function initCKEditor() {
    await loadCKEditor();

    const el = document.querySelector("#compose_body");
    if (el && window.ClassicEditor) {
        try {
            const editor = await window.ClassicEditor.create(el, {
                extraPlugins: [MyCustomUploadPlugin],
            });
            window.editorInstance = editor;
            return editor;
        } catch (error) {
            console.error("Error initializing CKEditor:", error);
            return null;
        }
    } else {
        console.warn("Editor element not found or CKEditor not available.");
        return null;
    }
}
