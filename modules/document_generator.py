# -*- coding: utf-8 -*-
"""
Module de génération de documents pour le publipostage
Version avec stockage PostgreSQL isolé par doc_id
"""
import os
import re
import base64
import threading
from typing import Dict, Any, List, Optional
from jinja2 import Environment, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from datetime import datetime
from playwright.sync_api import sync_playwright, BrowserContext

# ✅ IMPORTER LE STORAGE AVEC ISOLATION
from modules.template_storage import DatabaseTemplateStorage


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
    """Génère un nom de fichier à partir d'un pattern et des données"""
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
    """Gère la génération de documents de publipostage avec Playwright thread-safe"""
    
    def __init__(self, templates_folder: str = None):
        """
        Initialise le générateur de documents
        
        Args:
            templates_folder: Ignoré, conservé pour compatibilité
        """
        # ✅ INITIALISER LE STOCKAGE POSTGRESQL AVEC ISOLATION
        self.template_storage = DatabaseTemplateStorage()
        
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.jinja_env = SandboxedEnvironment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self.jinja_env.filters = {
            'date_fr': self.format_date_fr
        }
        
        self.fonts_cache = self._load_fonts_to_base64()
        self._thread_local = threading.local()
        
        print("✅ Générateur PDF initialisé avec Playwright (thread-safe + isolation)")
    
    def _get_browser_context(self) -> BrowserContext:
        """Récupère ou crée un contexte de navigateur pour le thread actuel"""
        if not hasattr(self._thread_local, 'context') or self._thread_local.context is None:
            print(f"[BROWSER] 🚀 Initialisation du navigateur pour le thread {threading.current_thread().name}")
            
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
                print(f"[BROWSER] ✅ Navigateur prêt pour le thread {threading.current_thread().name}")
            except Exception as e:
                print(f"[BROWSER] ❌ Erreur lors de l'initialisation : {e}")
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
            print(f"[BROWSER] ⚠️ Erreur lors du nettoyage : {e}")
    
    def _load_fonts_to_base64(self) -> Dict[str, str]:
        """Charge les fichiers de fonts et les convertit en Base64"""
        fonts_cache = {}
        fonts_dir = os.path.join(self.base_dir, 'static', 'fonts')
        
        if not os.path.exists(fonts_dir):
            print(f"[FONTS] ⚠️ Dossier fonts introuvable: {fonts_dir}")
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
                        print(f"[FONTS] ✅ {filename} chargée ({len(font_data)} octets)")
                except Exception as e:
                    print(f"[FONTS] ❌ Erreur lors du chargement de {filename}: {e}")
        
        return fonts_cache
    
    def is_timestamp(self, value: Any) -> bool:
        """Détecte si une valeur est un timestamp Unix"""
        if isinstance(value, bool):
            return False
        
        if isinstance(value, (int, float)):
            if 946684800 <= value <= 4000000000000:
                return True
        return False
    
    def format_date_fr(self, value: Any, format: str = "%d/%m/%Y") -> str:
        """Formate une date en français"""
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
        """Convertit automatiquement tous les timestamps Unix en dates françaises"""
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
        """Génère le CSS @font-face avec fonts embarquées en Base64"""
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
        """Génère l'en-tête avec le logo à gauche et le nom du service à droite"""
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
        """Génère la signature ancrée au contenu"""
        if not signature_data_url:
            return ""
        
        signature = f"""
        <div class="signature-container" style="margin-top: 10pt; text-align: right;">
            <img src="{signature_data_url}" alt="Signature" style="width: 100pt; height: auto; display: inline-block;">
        </div>
        """
        
        return signature
    
    # ✅ PASSER doc_id AU STORAGE
    def save_template(self, template_name: str, template_content: str, 
                 template_css: str = "", logo: Optional[str] = None,
                 signature: Optional[str] = None,
                 service_name: Optional[str] = None,
                 doc_id: Optional[str] = None) -> str:
        """Sauvegarde un template (avec isolation par doc_id)"""
        return self.template_storage.save_template(
            template_name=template_name,
            template_content=template_content,
            template_css=template_css,
            logo=logo,
            signature=signature,
            service_name=service_name,
            doc_id=doc_id  # ✅ NOUVEAU PARAMÈTRE
        )
    
    # ✅ PASSER doc_id AU STORAGE
    def load_template(self, template_name: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Charge un template (avec isolation par doc_id)"""
        return self.template_storage.load_template(
            template_name=template_name,
            doc_id=doc_id  # ✅ NOUVEAU PARAMÈTRE
        )
    
    # ✅ PASSER doc_id AU STORAGE
    def list_templates(self, doc_id: Optional[str] = None) -> List[str]:
        """Liste tous les templates (filtrés par doc_id)"""
        return self.template_storage.list_templates(
            doc_id=doc_id  # ✅ NOUVEAU PARAMÈTRE
        )
    
    # ✅ PASSER doc_id AU STORAGE
    def delete_template(self, template_name: str, doc_id: Optional[str] = None) -> str:
        """Supprime un template (avec isolation par doc_id)"""
        return self.template_storage.delete_template(
            template_name=template_name,
            doc_id=doc_id  # ✅ NOUVEAU PARAMÈTRE
        )
    
    def render_template(self, template_content: str, data: Dict[str, Any]) -> str:
        """Remplace les variables dans le template par les données"""
        try:
            dangerous_patterns = [
                r'{%\s*include',
                r'{%\s*import',
                r'{%\s*extends',
                r'{%\s*from',
                r'__',
                r'\.mro',
                r'\.subclasses',
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, template_content, re.IGNORECASE):
                    raise ValueError(f"Template contient du code potentiellement dangereux: {pattern}")
            
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
        """Génère le HTML complet avec CSS, logo, service et signature"""
        try:
            rendered_content = self.render_template(template_content, data)
            
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
            position: relative;
        }}
        
        p {{
            font-family: 'Marianne', sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            margin-top: 0;
            margin-bottom: 6pt;
        }}
        
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
            print(f"Erreur lors de la génération du HTML: {e}")
            raise
    
    def generate_pdf(self, html_content: str, output_path: str) -> str:
        """Génère un PDF à partir du HTML avec Playwright"""
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
                print(f"[PDF] ✅ Fichier créé: {output_path} ({file_size} octets)")
                return output_path
            else:
                raise Exception(f"Le fichier PDF n'a pas été créé: {output_path}")
            
        except Exception as e:
            print(f"[PDF] ❌ Erreur: {e}")
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
        """Génère plusieurs documents à partir d'une liste d'enregistrements"""
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
                    print(f"[BATCH] ❌ Erreur document {i}: {e}")
                    continue
        finally:
            self._cleanup_thread_browser()
        
        return generated_files