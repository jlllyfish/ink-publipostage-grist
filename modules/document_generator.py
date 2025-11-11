"""
Module de gÃ©nÃ©ration de documents pour le publipostage
Version simplifiÃ©e avec style "pied de page" dans l'Ã©diteur
"""
import os
import json
import re
import base64
import threading
from typing import Dict, Any, List, Optional
from jinja2 import Template, Environment
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Playwright


def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier pour le rendre valide"""
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(invalid_chars, '_', filename)
    filename = filename.strip()
    filename = filename.replace(' ', '_')
    filename = re.sub(r'_+', '_', filename)
    filename = filename.strip('_')
    
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:195] + ('.' + ext if ext else '')
    
    return filename


def generate_filename_from_pattern(pattern: str, data: Dict[str, Any], index: int = None) -> str:
    """GÃ©nÃ¨re un nom de fichier Ã  partir d'un pattern et des donnÃ©es"""
    if not pattern or pattern.strip() == '':
        pattern = "document"
    
    filename = pattern.strip()
    
    if index is not None:
        filename = filename.replace('{index}', str(index))
    
    for key, value in data.items():
        pattern_regex = r'{' + re.escape(key) + r'}'
        str_value = str(value or 'vide').strip()
        filename = re.sub(pattern_regex, str_value, filename)
    
    filename = re.sub(r'\s+', '_', filename)
    filename = sanitize_filename(filename)
    
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    
    return filename


class DocumentGenerator:
    """GÃ¨re la gÃ©nÃ©ration de documents de publipostage avec Playwright thread-safe"""
    
    def __init__(self, templates_folder: str):
        """Initialise le gÃ©nÃ©rateur de documents"""
        self.templates_folder = templates_folder
        os.makedirs(templates_folder, exist_ok=True)
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.jinja_env = Environment()
        self.jinja_env.filters['date_fr'] = self.format_date_fr
        
        # Charger les fonts en mÃ©moire
        self.fonts_cache = self._load_fonts_to_base64()
        
        # Pool de navigateurs par thread
        self._thread_local = threading.local()
        
        print("âœ… GÃ©nÃ©rateur PDF initialisÃ© avec Playwright (thread-safe)")
    
    def _get_browser_context(self) -> BrowserContext:
        """RÃ©cupÃ¨re ou crÃ©e un contexte de navigateur pour le thread actuel"""
        if not hasattr(self._thread_local, 'context') or self._thread_local.context is None:
            print(f"[BROWSER] ðŸš€ Initialisation du navigateur pour le thread {threading.current_thread().name}")
            
            try:
                self._thread_local.playwright = sync_playwright().start()
                self._thread_local.browser = self._thread_local.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )
                self._thread_local.context = self._thread_local.browser.new_context()
                print(f"[BROWSER] âœ… Navigateur prÃªt pour le thread {threading.current_thread().name}")
            except Exception as e:
                print(f"[BROWSER] âŒ Erreur lors de l'initialisation : {e}")
                raise
        
        return self._thread_local.context
    
    def _cleanup_thread_browser(self):
        """Ferme le navigateur du thread actuel"""
        try:
            if hasattr(self._thread_local, 'context') and self._thread_local.context:
                self._thread_local.context.close()
                self._thread_local.context = None
            
            if hasattr(self._thread_local, 'browser') and self._thread_local.browser:
                self._thread_local.browser.close()
                self._thread_local.browser = None
            
            if hasattr(self._thread_local, 'playwright') and self._thread_local.playwright:
                self._thread_local.playwright.stop()
                self._thread_local.playwright = None
        except Exception as e:
            print(f"[BROWSER] âš ï¸ Erreur lors du nettoyage : {e}")
    
    def _load_fonts_to_base64(self) -> Dict[str, str]:
        """Charge les fichiers de fonts et les convertit en Base64"""
        fonts_cache = {}
        fonts_dir = os.path.join(self.base_dir, 'static', 'fonts')
        
        if not os.path.exists(fonts_dir):
            print(f"[FONTS] âš ï¸ Dossier fonts introuvable: {fonts_dir}")
            return fonts_cache
        
        font_files = {
            'marianne_regular_woff2': 'Marianne-Regular.woff2',
            'marianne_regular_woff': 'Marianne-Regular.woff',
            'marianne_bold_woff2': 'Marianne-Bold.woff2',
            'marianne_bold_woff': 'Marianne-Bold.woff'
        }
        
        for key, filename in font_files.items():
            filepath = os.path.join(fonts_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        font_data = f.read()
                        mime_type = 'font/woff2' if filename.endswith('.woff2') else 'font/woff'
                        base64_data = base64.b64encode(font_data).decode('utf-8')
                        fonts_cache[key] = f"data:{mime_type};base64,{base64_data}"
                        print(f"[FONTS] âœ… {filename} chargÃ©e ({len(font_data)} octets)")
                except Exception as e:
                    print(f"[FONTS] âŒ Erreur lors du chargement de {filename}: {e}")
        
        return fonts_cache
    
    def is_timestamp(self, value: Any) -> bool:
        """DÃ©tecte si une valeur est un timestamp Unix"""
        if isinstance(value, bool):
            return False
        
        if isinstance(value, (int, float)):
            if 946684800 <= value <= 4000000000000:
                return True
        return False
    
    def format_date_fr(self, value: Any, format: str = "%d/%m/%Y") -> str:
        """Formate une date en franÃ§ais"""
        try:
            if isinstance(value, datetime):
                return value.strftime(format)
            
            if isinstance(value, (int, float)):
                if value > 10000000000:
                    timestamp = value / 1000
                else:
                    timestamp = value
                
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime(format)
            
            return str(value)
        except Exception as e:
            print(f"Erreur conversion date: {value} -> {e}")
            return str(value)
    
    def convert_timestamps_in_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convertit automatiquement tous les timestamps Unix en dates franÃ§aises"""
        converted_data = {}
        
        for key, value in data.items():
            if isinstance(value, bool):
                converted_data[key] = value
                continue
                
            if self.is_timestamp(value):
                converted_data[key] = self.format_date_fr(value)
            else:
                converted_data[key] = value
        
        return converted_data
    
    def get_font_face_css(self) -> str:
        """GÃ©nÃ¨re le CSS @font-face avec fonts embarquÃ©es en Base64"""
        if not self.fonts_cache:
            return ""
        
        font_css = f"""
        @font-face {{
            font-family: 'Marianne';
            src: url('{self.fonts_cache.get("marianne_regular_woff2", "")}') format('woff2'),
                 url('{self.fonts_cache.get("marianne_regular_woff", "")}') format('woff');
            font-weight: 400;
            font-style: normal;
        }}
        
        @font-face {{
            font-family: 'Marianne';
            src: url('{self.fonts_cache.get("marianne_bold_woff2", "")}') format('woff2'),
                 url('{self.fonts_cache.get("marianne_bold_woff", "")}') format('woff');
            font-weight: 700;
            font-style: normal;
        }}
        """
        
        return font_css
    
    def generate_entete_with_logo(self, logo_data_url: Optional[str] = None, 
                                   service_name: Optional[str] = None) -> str:
        """GÃ©nÃ¨re l'en-tÃªte avec le logo Ã  gauche et le nom du service Ã  droite"""
        if not logo_data_url and not service_name:
            return ""
        
        service_html = ""
        if service_name:
            service_lines = service_name.replace('\r\n', '\n').split('\n')
            service_html = '<br>'.join(service_lines)
        
        entete = f"""
        <div style="display: table; width: 100%; margin-bottom: 20pt;">
            <div style="display: table-row;">
                <div style="display: table-cell; width: 50%; vertical-align: top;">
                    {f'<img src="{logo_data_url}" alt="Logo" style="width: 80pt; height: auto; display: block;">' if logo_data_url else ''}
                </div>
                <div style="display: table-cell; width: 50%; vertical-align: top; text-align: right;">
                    {f'<div style="font-family: Marianne, sans-serif; font-size: 10pt; line-height: 1.3;">{service_html}</div>' if service_name else ''}
                </div>
            </div>
        </div>
        <hr style="border: none; border-top: 2pt solid #000091; margin: 15pt 0 20pt 0; padding: 0;" />
        """
        
        return entete
    
    def generate_signature(self, signature_data_url: Optional[str] = None) -> str:
        """GÃ©nÃ¨re la signature ancrÃ©e au contenu"""
        if not signature_data_url:
            return ""
        
        signature = f"""
        <div class="signature-container" style="margin-top: 10pt; text-align: right;">
            <img src="{signature_data_url}" alt="Signature" style="width: 100pt; height: auto; display: inline-block;">
        </div>
        """
        
        return signature
    
    def save_template(self, template_name: str, template_content: str, 
                 template_css: str = "", logo: Optional[str] = None,
                 signature: Optional[str] = None,
                 service_name: Optional[str] = None) -> str:
        """Sauvegarde un template de publipostage"""
        template_data = {
            'name': template_name,
            'content': template_content,
            'css': template_css,
            'logo': logo,
            'signature': signature,
            'service_name': service_name,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        filepath = os.path.join(self.templates_folder, f"{safe_name}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        
        print(f"âœ… Template sauvegardÃ©: {filepath}")
        
        return filepath
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Charge un template sauvegardé"""
        print(f"[LOAD] Template demandé: '{template_name}'")
        
        safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        filepath = os.path.join(self.templates_folder, f"{safe_name}.json")
        
        print(f"[LOAD] Chemin calculé: {filepath}")
        print(f"[LOAD] Fichier existe: {os.path.exists(filepath)}")
        
        # Liste tous les fichiers du dossier
        if os.path.exists(self.templates_folder):
            print(f"[LOAD] Fichiers dans {self.templates_folder}:")
            for f in os.listdir(self.templates_folder):
                print(f"  - {f}")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Template '{template_name}' introuvable à {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            'template_content': data.get('content', ''),
            'template_css': data.get('css', ''),
            'logo': data.get('logo'),
            'signature': data.get('signature'),
            'service_name': data.get('service_name'),
            'table_id': data.get('table_id')
        }
    
    def list_templates(self) -> List[str]:
        """Liste tous les templates disponibles"""
        templates = []
        if not os.path.exists(self.templates_folder):
            return templates
            
        for filename in os.listdir(self.templates_folder):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.templates_folder, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        templates.append(data['name'])
                except Exception as e:
                    continue
        return templates
    
     # âœ… AJOUTEZ CETTE NOUVELLE MÃ‰THODE ICI
    def delete_template(self, template_name: str) -> str:
        """Supprime un template sauvegardÃ©"""
        safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        filepath = os.path.join(self.templates_folder, f"{safe_name}.json")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Template '{template_name}' introuvable")
        
        os.remove(filepath)
        print(f"ðŸ—‘ï¸ Template supprimÃ©: {filepath}")
        
        return filepath
    
    def render_template(self, template_content: str, data: Dict[str, Any]) -> str:
        """Remplace les variables dans le template par les donnÃ©es"""
        try:
            converted_data = self.convert_timestamps_in_data(data)
            template = self.jinja_env.from_string(template_content)
            return template.render(**converted_data)
        except Exception as e:
            print(f"Erreur lors du rendu du template: {e}")
            raise
    
    def generate_html(self, template_content: str, template_css: str, 
                  data: Dict[str, Any], logo: Optional[str] = None,
                  signature: Optional[str] = None,
                  service_name: Optional[str] = None) -> str:
        """GÃ©nÃ¨re le HTML complet avec CSS, logo, service et signature"""
        try:
            rendered_content = self.render_template(template_content, data)
            
            # Nettoyage du HTML
            rendered_content = re.sub(r'style="color:\s*rgb\([^)]+\);?"', '', rendered_content)
            rendered_content = re.sub(r'\s*style=""\s*', ' ', rendered_content)
            
            entete_html = self.generate_entete_with_logo(logo, service_name)
            signature_html = self.generate_signature(signature)
            
            font_face_css = self.get_font_face_css()
            
            html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Document de publipostage</title>
    <style>
        {font_face_css}
        
        body {{
            font-family: 'Marianne', 'Arial', 'Helvetica', sans-serif;
            line-height: 1.6;
            color: #000000;
            margin: 2cm;
        }}
        
        p {{
            font-family: 'Marianne', sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            margin-top: 0;
            margin-bottom: 6pt;
        }}
        
        /* Formats de taille de Quill */
        .ql-size-8pt {{
            font-size: 8pt !important;
            color: #666666 !important;
        }}
        
        .ql-size-18pt {{
            font-size: 18pt;
        }}
        
        .ql-size-24pt {{
            font-size: 24pt;
        }}
        
        /* Style "pied de page" pour l'Ã©diteur */
        .footer-style {{
            font-family: 'Marianne', sans-serif !important;
            font-size: 8pt !important;
            font-weight: 400 !important;
            color: #666666 !important;
            line-height: 1.3 !important;
        }}
        
        .ql-align-left {{
            text-align: left !important;
        }}
        
        .ql-align-center {{
            text-align: center !important;
        }}
        
        .ql-align-right {{
            text-align: right !important;
        }}
        
        .ql-align-justify {{
            text-align: justify !important;
        }}
        
        h1 {{
            font-family: 'Marianne', sans-serif;
            font-size: 24pt;
            font-weight: 700;
            margin-top: 12pt;
            margin-bottom: 6pt;
        }}
        
        h2 {{
            font-family: 'Marianne', sans-serif;
            font-size: 18pt;
            font-weight: 700;
            margin-top: 10pt;
            margin-bottom: 5pt;
        }}
        
        h3 {{
            font-family: 'Marianne', sans-serif;
            font-size: 14pt;
            font-weight: 700;
            margin-top: 8pt;
            margin-bottom: 4pt;
        }}
        
        strong, b {{
            font-weight: 700;
        }}
        
        em, i {{
            font-style: italic;
        }}
        
        u {{
            text-decoration: underline;
        }}
        
        ul, ol {{
            font-family: 'Marianne', sans-serif;
            font-size: 11pt;
            margin-bottom: 6pt;
            padding-left: 20pt;
            line-height: 1.4;
        }}
        
        li {{
            margin-bottom: 3pt;
        }}
        
        table {{
            font-family: 'Marianne', sans-serif;
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10pt;
            font-size: 11pt;
        }}
        
        th, td {{
            border: 1pt solid #ccc;
            padding: 5pt;
            text-align: left;
        }}
        
        th {{
            background-color: #f0f0f0;
            font-weight: 700;
        }}
        
        .signature-container {{
            margin-top: 30pt;
            text-align: right;
        }}
        
        {template_css}
    </style>
</head>
<body>
    {entete_html}
    <div class="contenu">
        {rendered_content}
        {signature_html}
    </div>
</body>
</html>"""
            
            return html
        except Exception as e:
            print(f"Erreur lors de la gÃ©nÃ©ration du HTML: {e}")
            raise
    
    def generate_pdf(self, html_content: str, output_path: str) -> str:
        """GÃ©nÃ¨re un PDF Ã  partir du HTML avec Playwright"""
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            context = self._get_browser_context()
            page = context.new_page()
            
            try:
                page.set_content(html_content, wait_until='domcontentloaded', timeout=30000)
                page.evaluate("() => document.fonts.ready")
                page.wait_for_timeout(500)
                
                page.pdf(
                    path=output_path,
                    format='A4',
                    margin={
                        'top': '0',
                        'right': '0',
                        'bottom': '0',
                        'left': '0'
                    },
                    print_background=True
                )
                
            finally:
                page.close()
            
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"[PDF] âœ… Fichier crÃ©Ã©: {output_path} ({file_size} octets)")
                return output_path
            else:
                raise Exception(f"Le fichier PDF n'a pas Ã©tÃ© crÃ©Ã©: {output_path}")
            
        except Exception as e:
            print(f"[PDF] âŒ Erreur: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def generate_multiple_documents(self, template_content: str, template_css: str,
                               records: List[Dict[str, Any]], 
                               output_folder: str,
                               logo: Optional[str] = None,
                               signature: Optional[str] = None,
                               service_name: Optional[str] = None,
                               filename_pattern: str = "document_{index}") -> List[str]:
        """GÃ©nÃ¨re plusieurs documents Ã  partir d'une liste d'enregistrements"""
        output_folder = os.path.abspath(output_folder)
        os.makedirs(output_folder, exist_ok=True)
        
        generated_files = []
        
        try:
            for i, record in enumerate(records, 1):
                try:
                    filename = generate_filename_from_pattern(filename_pattern, record, i)
                    output_path = os.path.abspath(os.path.join(output_folder, filename))
                    
                    html = self.generate_html(
                        template_content, template_css, record, 
                        logo, signature, service_name
                    )
                    self.generate_pdf(html, output_path)
                    
                    if os.path.exists(output_path):
                        generated_files.append(output_path)
                        
                except Exception as e:
                    print(f"[BATCH] âŒ Erreur document {i}: {e}")
                    continue
        finally:
            self._cleanup_thread_browser()
        
        return generated_files