# -*- coding: utf-8 -*-
"""
Application Flask principale pour le publipostage Grist
"""
import os
import sys
import json
import zipfile
import traceback
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from modules.grist_connector import GristConnector
from io import BytesIO
import time
from modules.document_generator import DocumentGenerator, generate_filename_from_pattern

load_dotenv()
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['TEMPLATES_FOLDER'] = os.getenv('TEMPLATES_FOLDER', 'templates_publipostage')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMPLATES_FOLDER'], exist_ok=True)

# 🆕 MODIFIÉ : Grist n'est plus initialisé globalement
# Il sera créé dynamiquement pour chaque requête avec les credentials fournis
grist = None

doc_gen = DocumentGenerator(app.config['TEMPLATES_FOLDER'])
print(f"✓ Générateur de documents initialisé")


# 🆕 NOUVELLE FONCTION : Créer une instance Grist temporaire
def create_grist_instance(api_key, doc_id):
    """Créer une instance GristConnector avec les credentials fournis"""
    try:
        return GristConnector(
            api_key=api_key,
            doc_id=doc_id,
            server=os.getenv('GRIST_SERVER', 'https://grist.numerique.gouv.fr')
        )
    except Exception as e:
        print(f"✗ Erreur création instance Grist : {e}")
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/test')
def test_page():
    return render_template('test.html')


# 🆕 MODIFIÉ : Accepte api_key et doc_id en POST
@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        api_key = data.get('api_key')
        doc_id = data.get('doc_id')
        
        if not api_key or not doc_id:
            return jsonify({
                'success': False,
                'message': 'Clé API et Doc ID requis'
            }), 400
        
        # Créer instance temporaire
        temp_grist = create_grist_instance(api_key, doc_id)
        
        if not temp_grist:
            return jsonify({
                'success': False,
                'message': 'Impossible de créer la connexion Grist'
            }), 500
        
        success = temp_grist.test_connection()
        if success:
            return jsonify({
                'success': True,
                'message': 'Connexion à Grist réussie'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Échec de la connexion à Grist'
            }), 500
    except Exception as e:
        print(f"Erreur test connexion: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


# 🆕 MODIFIÉ : Accepte api_key et doc_id en POST
@app.route('/api/tables', methods=['POST'])
def get_tables():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        api_key = data.get('api_key')
        doc_id = data.get('doc_id')
        
        if not api_key or not doc_id:
            return jsonify({
                'success': False,
                'message': 'Clé API et Doc ID requis'
            }), 400
        
        temp_grist = create_grist_instance(api_key, doc_id)
        
        if not temp_grist:
            return jsonify({
                'success': False,
                'message': 'Grist non initialisé'
            }), 500
            
        tables = temp_grist.get_tables()
        return jsonify({
            'success': True,
            'tables': tables
        })
    except Exception as e:
        print(f"Erreur get_tables: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


# 🆕 MODIFIÉ : Accepte api_key et doc_id en POST
@app.route('/api/columns/<table_id>', methods=['POST'])
def get_columns(table_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        api_key = data.get('api_key')
        doc_id = data.get('doc_id')
        
        if not api_key or not doc_id:
            return jsonify({
                'success': False,
                'message': 'Clé API et Doc ID requis'
            }), 400
        
        temp_grist = create_grist_instance(api_key, doc_id)
        
        if not temp_grist:
            return jsonify({
                'success': False,
                'message': 'Grist non initialisé'
            }), 500
            
        columns = temp_grist.get_columns(table_id)
        return jsonify({
            'success': True,
            'columns': columns
        })
    except Exception as e:
        print(f"Erreur get_columns: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


# 🆕 MODIFIÉ : Accepte api_key et doc_id en POST
@app.route('/api/records/<table_id>', methods=['POST'])
def get_records(table_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        api_key = data.get('api_key')
        doc_id = data.get('doc_id')
        
        if not api_key or not doc_id:
            return jsonify({
                'success': False,
                'message': 'Clé API et Doc ID requis'
            }), 400
        
        temp_grist = create_grist_instance(api_key, doc_id)
        
        if not temp_grist:
            return jsonify({
                'success': False,
                'message': 'Grist non initialisé'
            }), 500
            
        limit = request.args.get('limit', type=int)
        apply_filter = request.args.get('filter', 'false').lower() == 'true'
        
        records = temp_grist.get_records(table_id, limit)
        original_count = len(records)
        
        if apply_filter:
            filter_column = app.config.get('PDF_FILTER_COLUMN', 'Pdf_print')
            
            filtered_records = []
            for i, record in enumerate(records, 1):
                value = record.get(filter_column)
                is_bool = isinstance(value, bool)
                
                if is_bool and value is True:
                    filtered_records.append(record)
            
            return jsonify({
                'success': True,
                'records': filtered_records,
                'count': len(filtered_records),
                'total_count': original_count,
                'filtered': True,
                'filter_column': filter_column
            })
        
        return jsonify({
            'success': True,
            'records': records,
            'count': len(records),
            'filtered': False
        })
        
    except Exception as e:
        print(f"Erreur get_records: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@app.route('/api/preview', methods=['POST'])
def preview_document():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        template_content = data.get('template_content', '')
        template_css = data.get('template_css', '')
        record_data = data.get('record_data', {})
        logo = data.get('logo')
        signature = data.get('signature')
        service_name = data.get('service_name')
        
        if not template_content:
            return jsonify({
                'success': False,
                'message': 'Le template est vide'
            }), 400
        
        html = doc_gen.generate_html(
            template_content, template_css, record_data, 
            logo, signature, service_name
        )
        
        return jsonify({
            'success': True,
            'html': html
        })
    except Exception as e:
        print(f"Erreur preview: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@app.route('/api/save-template', methods=['POST'])
def save_template():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        template_name = data.get('template_name')
        template_content = data.get('template_content')
        template_css = data.get('template_css', '')
        logo = data.get('logo')
        signature = data.get('signature')
        service_name = data.get('service_name')
        
        if not template_name or not template_content:
            return jsonify({
                'success': False,
                'message': 'Nom et contenu du template requis'
            }), 400
        
        filepath = doc_gen.save_template(
            template_name, template_content, template_css, 
            logo, signature, service_name
        )
        
        return jsonify({
            'success': True,
            'message': 'Template sauvegardé avec succès',
            'filepath': filepath
        })
    except Exception as e:
        print(f"Erreur save_template: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@app.route('/api/templates', methods=['GET'])
def list_templates():
    try:
        templates = doc_gen.list_templates()
        return jsonify({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        print(f"Erreur list_templates: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@app.route('/api/template/<template_name>', methods=['GET'])
def load_template(template_name):
    try:
        template_data = doc_gen.load_template(template_name)
        return jsonify({
            'success': True,
            'template': template_data
        })
    except Exception as e:
        print(f"Erreur load_template: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/template/<template_name>', methods=['DELETE'])
def delete_template(template_name):
    try:
        filepath = doc_gen.delete_template(template_name)
        return jsonify({
            'success': True,
            'message': f'Template "{template_name}" supprimé avec succès'
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'message': 'Template introuvable'
        }), 404
    except Exception as e:
        print(f"Erreur delete_template: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        template_content = data.get('template_content')
        template_css = data.get('template_css', '')
        record_data = data.get('record_data')
        logo = data.get('logo')
        signature = data.get('signature')
        service_name = data.get('service_name')
        filename_pattern = data.get('filename_pattern', 'document')
        
        if not template_content:
            return jsonify({
                'success': False,
                'message': 'Template vide'
            }), 400
        
        if not record_data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée fournie'
            }), 400
        
        html = doc_gen.generate_html(
            template_content, template_css, record_data, 
            logo, signature, service_name
        )
        
        filename = generate_filename_from_pattern(filename_pattern, record_data)
        print(f"✅ Nom de fichier généré : '{filename}'")
        
        output_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        doc_gen.generate_pdf(html, output_path)
        
        if not os.path.exists(output_path):
            return jsonify({
                'success': False,
                'message': 'Le PDF n\'a pas été créé'
            }), 500
        
        print(f"✅ Envoi du fichier: {output_path}")
        print(f"✅ Nom de téléchargement: {filename}")
        
        response = send_file(
            output_path,
            mimetype='application/pdf',
            as_attachment=True
        )
        
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"Erreur generate_pdf: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


# 🆕 MODIFIÉ : Accepte api_key et doc_id
@app.route('/api/generate-multiple', methods=['POST'])
def generate_multiple():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Aucune donnée reçue'
            }), 400
        
        template_content = data.get('template_content')
        template_css = data.get('template_css', '')
        table_id = data.get('table_id')
        logo = data.get('logo')
        signature = data.get('signature')
        service_name = data.get('service_name')
        filename_pattern = data.get('filename_pattern', 'document_{index}')
        apply_filter = data.get('apply_filter', False)
        
        # 🆕 RÉCUPÉRER LES CREDENTIALS
        api_key = data.get('api_key')
        doc_id = data.get('doc_id')
        
        if not api_key or not doc_id:
            return jsonify({
                'success': False,
                'message': 'Clé API et Doc ID requis'
            }), 400
        
        if not template_content:
            return jsonify({
                'success': False,
                'message': 'Template vide'
            }), 400
        
        if not table_id:
            return jsonify({
                'success': False,
                'message': 'Table non spécifiée'
            }), 400
        
        # 🆕 CRÉER INSTANCE TEMPORAIRE
        temp_grist = create_grist_instance(api_key, doc_id)
        
        if not temp_grist:
            return jsonify({
                'success': False,
                'message': 'Grist non initialisé'
            }), 500
        
        records = temp_grist.get_records(table_id)
        total_records = len(records)
        
        if apply_filter:
            filter_column = app.config.get('PDF_FILTER_COLUMN', 'Pdf_print')
            
            filtered_records = []
            for i, record in enumerate(records, 1):
                value = record.get(filter_column)
                is_bool = isinstance(value, bool)
                
                if is_bool and value is True:
                    filtered_records.append(record)
            
            records = filtered_records
            print(f"\n📊 {len(records)}/{total_records} documents seront générés\n")
        
        if not records:
            return jsonify({
                'success': False,
                'message': f'Aucun enregistrement trouvé avec {filter_column}=True' if apply_filter else 'Aucun enregistrement trouvé'
            }), 404
        
        output_folder = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], 'batch'))
        os.makedirs(output_folder, exist_ok=True)
        
        # Générer les PDFs
        files = doc_gen.generate_multiple_documents(
            template_content, 
            template_css, 
            records, 
            output_folder,
            logo,
            signature,
            service_name,
            filename_pattern
        )
        
        # Vérifier que les fichiers existent
        existing_files = []
        for filepath in files:
            abs_path = os.path.abspath(filepath)
            if os.path.exists(abs_path):
                existing_files.append(abs_path)
        
        if len(existing_files) == 0:
            return jsonify({
                'success': False,
                'message': f'Erreur : Aucun fichier créé dans {output_folder}'
            }), 500
        
        # Créer un ZIP en mémoire
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filepath in existing_files:
                arcname = os.path.basename(filepath)
                zip_file.write(filepath, arcname)
        
        zip_buffer.seek(0)
        
        # Nettoyer les fichiers temporaires
        for filepath in existing_files:
            try:
                os.remove(filepath)
            except:
                pass
        
        # Retourner le ZIP
        zip_filename = f'publipostage_{table_id}_{int(time.time())}.zip'
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        print(f"Erreur generate_multiple: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/config/filter-column', methods=['GET'])
def get_filter_column():
    return jsonify({
        'success': True,
        'filter_column': app.config.get('PDF_FILTER_COLUMN', 'Pdf_print')
    })


@app.route('/api/debug', methods=['GET'])
def debug():
    return jsonify({
        'grist_connected': grist is not None,
        'grist_server': os.getenv('GRIST_SERVER', 'https://grist.numerique.gouv.fr'),
        'grist_doc_id': os.getenv('GRIST_DOC_ID', 'NON DEFINI'),
        'grist_api_key_set': bool(os.getenv('GRIST_API_KEY')),
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'templates_folder': app.config['TEMPLATES_FOLDER'],
        'templates_folder_exists': os.path.exists(app.config['TEMPLATES_FOLDER'])
    })


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 DÉMARRAGE DE L'APPLICATION")
    print("="*50)
    print(f"✓ Flask initialisé")
    print(f"✓ Dossier uploads: {app.config['UPLOAD_FOLDER']}")
    print(f"✓ Dossier templates: {app.config['TEMPLATES_FOLDER']}")
    print(f"✓ Mode dynamique : API key et Doc ID fournis par l'utilisateur")
    
    print("\n📍 Application disponible sur: http://localhost:5000")
    print("📍 Page de test simple: http://localhost:5000/test")
    print("📍 Page de debug: http://localhost:5000/api/debug")
    print("="*50 + "\n")
    
    app.run(
        debug=False,
        host='0.0.0.0',
        port=5000,
        use_reloader=False
    )