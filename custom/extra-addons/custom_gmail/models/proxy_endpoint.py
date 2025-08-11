# Add this to your Odoo controller (e.g., in your custom module)

from odoo import http
from odoo.http import request
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class EmailAnalyzeProxy(http.Controller):
    
    @http.route('/analyze_email_proxy', type='json', auth='user', methods=['POST'])
    def analyze_email_proxy(self):
        try:
            data = request.jsonrequest
            
            # Get parameters from the request
            email_body = data.get('body', '')
            subject = data.get('subject', 'No Subject')
            
            if not email_body:
                return {'error': 'No email body provided'}
            
            # Prepare the payload for the Flask API
            full_prompt = f"please analyze the email:\n{email_body}\n explain in detail, include code snippets if applicable, and provide a step-by-step guide if needed."
            
            payload = {
                'text': full_prompt,
                'email': 'lebadung@wsoftpro.com',  # You can get this from session or config
                'image_base64': None
            }
            
            # Make request to Flask API
            api_url = "http://192.168.1.51:9999/api/status"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer zLrA3pN7'  # You should store this securely
            }
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'result': result.get('result', 'No result'),
                    'message': 'Analysis completed successfully'
                }
            else:
                _logger.error(f"Flask API returned status {response.status_code}: {response.text}")
                return {
                    'error': f'API request failed with status {response.status_code}'
                }
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request to Flask API failed: {str(e)}")
            return {'error': f'Failed to connect to analysis service: {str(e)}'}
        except Exception as e:
            _logger.error(f"Unexpected error in analyze_email_proxy: {str(e)}")
            return {'error': f'Unexpected error: {str(e)}'}