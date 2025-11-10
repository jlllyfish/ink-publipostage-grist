"""
Module de connexion à l'API Grist avec gestion des timeouts
"""
import requests
from typing import List, Dict, Any, Optional


class GristConnector:
    """Gère la connexion et les requêtes à l'API Grist"""
    
    def __init__(self, api_key: str, doc_id: str, server: str = "https://grist.numerique.gouv.fr"):
        """
        Initialise la connexion Grist
        
        Args:
            api_key: Clé API Grist
            doc_id: ID du document Grist
            server: URL du serveur Grist
        """
        self.api_key = api_key
        self.doc_id = doc_id
        self.server = server.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        # ✅ NOUVEAU : Timeout par défaut (connexion, lecture)
        self.timeout = (10, 30)  # 10s connexion, 30s lecture
    
    def get_tables(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des tables du document
        
        Returns:
            Liste des tables
        """
        url = f"{self.server}/api/docs/{self.doc_id}/tables"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get('tables', [])
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout lors de la récupération des tables depuis {self.server}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de la récupération des tables : {e}")
            raise
    
    def get_columns(self, table_id: str) -> List[str]:
        """
        Récupère les noms des colonnes d'une table
        
        Args:
            table_id: ID de la table
            
        Returns:
            Liste des noms de colonnes
        """
        url = f"{self.server}/api/docs/{self.doc_id}/tables/{table_id}/columns"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            columns = response.json().get('columns', [])
            return [col['id'] for col in columns if not col['id'].startswith('gristHelper_')]
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout lors de la récupération des colonnes de {table_id}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de la récupération des colonnes : {e}")
            raise
    
    def get_records(self, table_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Récupère les enregistrements d'une table
        
        Args:
            table_id: ID de la table
            limit: Nombre maximum d'enregistrements (None = tous)
            
        Returns:
            Liste des enregistrements
        """
        url = f"{self.server}/api/docs/{self.doc_id}/tables/{table_id}/records"
        params = {}
        if limit:
            params['limit'] = limit
        
        try:
            # ✅ Timeout plus long pour les grandes tables
            timeout = (10, 60) if not limit or limit > 100 else self.timeout
            response = requests.get(url, headers=self.headers, params=params, timeout=timeout)
            response.raise_for_status()
            
            records = response.json().get('records', [])
            # Convertir le format Grist en format simple
            return [record['fields'] for record in records]
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout lors de la récupération des enregistrements de {table_id}")
            print(f"   Essayez de limiter le nombre de lignes ou vérifiez votre connexion réseau")
            raise
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de la récupération des enregistrements : {e}")
            raise
    
    def get_record_by_id(self, table_id: str, record_id: int) -> Dict[str, Any]:
        """
        Récupère un enregistrement spécifique
        
        Args:
            table_id: ID de la table
            record_id: ID de l'enregistrement
            
        Returns:
            L'enregistrement
        """
        url = f"{self.server}/api/docs/{self.doc_id}/tables/{table_id}/records"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            records = response.json().get('records', [])
            for record in records:
                if record['id'] == record_id:
                    return record['fields']
            
            raise ValueError(f"Enregistrement {record_id} non trouvé")
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout lors de la récupération de l'enregistrement {record_id}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de la récupération de l'enregistrement : {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Teste la connexion à Grist
        
        Returns:
            True si la connexion fonctionne
        """
        try:
            url = f"{self.server}/api/docs/{self.doc_id}"
            # ✅ Timeout court pour le test (5s connexion, 10s lecture)
            response = requests.get(url, headers=self.headers, timeout=(5, 10))
            response.raise_for_status()
            print(f"✅ Connexion à Grist réussie : {self.server}")
            return True
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout lors du test de connexion à {self.server}")
            print(f"   Vérifiez votre connexion réseau ou le proxy")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur de connexion : {e}")
            return False