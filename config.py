"""
Configuration de l'application
"""
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


class Config:
    """Configuration de base"""
    
    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    ENV = os.getenv('FLASK_ENV', 'development')
    
    # Grist
    GRIST_API_KEY = os.getenv('GRIST_API_KEY')
    GRIST_DOC_ID = os.getenv('GRIST_DOC_ID')
    GRIST_TABLE_ID = os.getenv('GRIST_TABLE_ID')
    GRIST_SERVER = os.getenv('GRIST_SERVER', 'https://grist.numerique.gouv.fr')

    # ✅ NOUVEAU : Colonne de filtre pour la génération PDF
    PDF_FILTER_COLUMN = os.getenv('PDF_FILTER_COLUMN', 'Pdf_print')
    
    # Dossiers
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    TEMPLATES_FOLDER = os.getenv('TEMPLATES_FOLDER', 'templates_publipostage')
    
    # Limites
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file size
    
    @staticmethod
    def validate():
        """Valide que les variables essentielles sont définies"""
        required_vars = [
            'GRIST_API_KEY',
            'GRIST_DOC_ID'
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            raise ValueError(
                f"Variables d'environnement manquantes : {', '.join(missing)}\n"
                "Veuillez configurer votre fichier .env"
            )
        
        return True


class DevelopmentConfig(Config):
    """Configuration de développement"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Configuration de production"""
    DEBUG = False
    TESTING = False
    
    # En production, la clé secrète doit être définie
    @staticmethod
    def validate():
        Config.validate()
        if Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError(
                "FLASK_SECRET_KEY doit être définie en production !"
            )


class TestingConfig(Config):
    """Configuration de test"""
    TESTING = True
    DEBUG = True


# Mapping des configurations
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Retourne la configuration appropriée"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    return config_by_name.get(config_name, DevelopmentConfig)