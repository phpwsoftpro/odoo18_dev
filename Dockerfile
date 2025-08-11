FROM odoo:18.0

USER root

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN pip install --break-system-packages --no-deps --no-cache-dir msal openai

USER odoo
