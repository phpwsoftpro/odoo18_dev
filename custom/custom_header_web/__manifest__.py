{
    "name": "Header Web Custom Theme",
    "version": "1.0",
    "description": "Custom website mockup theme based on Figma prototype",
    "website": "https://crm2.wsoftpro.com",
    "category": "Website",
    "depends": ["website", "web"],
    "data": [
        # "views/assets.xml",
        "views/header.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "custom_header_web/static/src/css/style.css",
        ],
    },
    "installable": True,
    "application": False,
}
