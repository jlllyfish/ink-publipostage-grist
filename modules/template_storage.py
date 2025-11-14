# -*- coding: utf-8 -*-
"""
Module de stockage des templates en base de données PostgreSQL
Version avec isolation par doc_id
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
from datetime import datetime


class DatabaseTemplateStorage:
    """Gestion du stockage des templates dans PostgreSQL avec isolation par doc_id"""
    
    def __init__(self, db_url: str = None):
        """
        Initialise la connexion à la base de données
        
        Args:
            db_url: URL de connexion PostgreSQL (si None, utilise DATABASE_URL de l'env)
        """
        self.db_url = db_url or os.getenv('DATABASE_URL')
        
        if not self.db_url:
            raise ValueError("DATABASE_URL non définie. Impossible d'initialiser le stockage.")
        
        # Tester la connexion
        self._test_connection()
        print("✅ Stockage PostgreSQL initialisé (avec isolation par doc_id)")
    
    def _test_connection(self):
        """Teste la connexion et crée la table si nécessaire"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            # Vérifier si la table existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'templates'
                );
            """)
            
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                print("⚠️ Table 'templates' inexistante. Création automatique...")
                self._create_table(cur)
                conn.commit()
                print("✅ Table 'templates' créée")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erreur connexion PostgreSQL: {e}")
            raise
    
    def _create_table(self, cur):
        """Crée la table templates si elle n'existe pas"""
        cur.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                content TEXT NOT NULL,
                css TEXT DEFAULT '',
                logo TEXT,
                signature TEXT,
                service_name TEXT,
                table_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name);
            CREATE INDEX IF NOT EXISTS idx_templates_updated_at ON templates(updated_at DESC);
        """)
    
    def _get_connection(self):
        """Retourne une nouvelle connexion à la base de données"""
        return psycopg2.connect(self.db_url)
    
    def _make_unique_name(self, template_name: str, doc_id: str = None) -> str:
        """
        Crée un nom unique en préfixant avec doc_id
        
        Args:
            template_name: Nom du template saisi par l'utilisateur
            doc_id: ID du document Grist (pour isolation)
        
        Returns:
            Nom unique préfixé (ex: "ABC123_Facture")
        """
        # Nettoyer le nom
        safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        
        # ✅ Préfixer avec doc_id si fourni
        if doc_id and doc_id.strip():
            return f"{doc_id}_{safe_name}"
        
        return safe_name
    
    def _strip_doc_id_prefix(self, unique_name: str, doc_id: str = None) -> str:
        """
        Retire le préfixe doc_id du nom pour l'affichage
        
        Args:
            unique_name: Nom stocké en base (ex: "ABC123_Facture")
            doc_id: ID du document Grist
        
        Returns:
            Nom sans préfixe (ex: "Facture")
        """
        if doc_id and unique_name.startswith(f"{doc_id}_"):
            return unique_name[len(doc_id) + 1:]  # +1 pour le underscore
        return unique_name
    
    def save_template(self, template_name: str, template_content: str, 
                      template_css: str = "", logo: str = None,
                      signature: str = None, service_name: str = None,
                      table_id: str = None, doc_id: str = None) -> str:
        """
        Sauvegarde un template dans PostgreSQL avec isolation par doc_id
        
        Args:
            template_name: Nom du template (sera préfixé avec doc_id)
            template_content: Contenu HTML
            template_css: CSS personnalisé
            logo: Logo en base64
            signature: Signature en base64
            service_name: Nom du service
            table_id: ID de la table Grist associée
            doc_id: ID du document Grist (pour isolation) ✅ NOUVEAU
        
        Returns:
            Message de confirmation
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # ✅ Créer un nom unique avec doc_id
            unique_name = self._make_unique_name(template_name, doc_id)
            
            print(f"[STORAGE] Sauvegarde: '{template_name}' → '{unique_name}'")
            
            # INSERT ou UPDATE si existe déjà
            cur.execute("""
                INSERT INTO templates (name, content, css, logo, signature, service_name, table_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (name) 
                DO UPDATE SET 
                    content = EXCLUDED.content,
                    css = EXCLUDED.css,
                    logo = EXCLUDED.logo,
                    signature = EXCLUDED.signature,
                    service_name = EXCLUDED.service_name,
                    table_id = EXCLUDED.table_id,
                    updated_at = NOW()
                RETURNING id;
            """, (
                unique_name,
                template_content,
                template_css or '',
                logo,
                signature,
                service_name,
                table_id
            ))
            
            template_id = cur.fetchone()[0]
            conn.commit()
            
            print(f"✅ Template '{template_name}' sauvegardé (ID: {template_id}, doc_id: {doc_id})")
            
            return f"database://templates/{template_id}"
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Erreur sauvegarde template: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def load_template(self, template_name: str, doc_id: str = None) -> Dict[str, Any]:
        """
        Charge un template depuis PostgreSQL avec isolation par doc_id
        
        Args:
            template_name: Nom du template (sans préfixe)
            doc_id: ID du document Grist (pour isolation) ✅ NOUVEAU
        
        Returns:
            Dictionnaire avec les données du template
        
        Raises:
            FileNotFoundError: Si le template n'existe pas
        """
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # ✅ Créer le nom unique avec doc_id
            unique_name = self._make_unique_name(template_name, doc_id)
            
            print(f"[STORAGE] Chargement: '{template_name}' → '{unique_name}'")
            
            cur.execute("""
                SELECT content, css, logo, signature, service_name, table_id
                FROM templates 
                WHERE name = %s
            """, (unique_name,))
            
            row = cur.fetchone()
            
            if not row:
                raise FileNotFoundError(f"Template '{template_name}' introuvable (doc_id: {doc_id})")
            
            print(f"✅ Template '{template_name}' chargé")
            
            return {
                'template_content': row['content'],
                'template_css': row['css'] or '',
                'logo': row['logo'],
                'signature': row['signature'],
                'service_name': row['service_name'],
                'table_id': row['table_id']
            }
            
        finally:
            cur.close()
            conn.close()
    
    def list_templates(self, doc_id: str = None) -> List[str]:
        """
        Liste tous les templates disponibles pour un doc_id
        
        Args:
            doc_id: ID du document Grist (pour filtrage) ✅ NOUVEAU
        
        Returns:
            Liste des noms de templates (sans préfixe doc_id, triés par date)
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            if doc_id and doc_id.strip():
                # ✅ Filtrer par doc_id
                pattern = f"{doc_id}_%"
                print(f"[STORAGE] Liste templates pour doc_id: {doc_id}")
                
                cur.execute("""
                    SELECT name 
                    FROM templates 
                    WHERE name LIKE %s
                    ORDER BY updated_at DESC
                """, (pattern,))
            else:
                # Mode legacy: tous les templates
                print("[STORAGE] Liste TOUS les templates (aucun doc_id)")
                
                cur.execute("""
                    SELECT name 
                    FROM templates 
                    ORDER BY updated_at DESC
                """)
            
            results = cur.fetchall()
            
            # ✅ Retirer le préfixe doc_id pour l'affichage
            templates = [self._strip_doc_id_prefix(row[0], doc_id) for row in results]
            
            print(f"✅ {len(templates)} template(s) trouvé(s)")
            
            return templates
            
        finally:
            cur.close()
            conn.close()
    
    def delete_template(self, template_name: str, doc_id: str = None) -> str:
        """
        Supprime un template avec isolation par doc_id
        
        Args:
            template_name: Nom du template (sans préfixe)
            doc_id: ID du document Grist (pour isolation) ✅ NOUVEAU
        
        Returns:
            Message de confirmation
        
        Raises:
            FileNotFoundError: Si le template n'existe pas
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # ✅ Créer le nom unique avec doc_id
            unique_name = self._make_unique_name(template_name, doc_id)
            
            print(f"[STORAGE] Suppression: '{template_name}' → '{unique_name}'")
            
            cur.execute("""
                DELETE FROM templates 
                WHERE name = %s
                RETURNING id
            """, (unique_name,))
            
            deleted = cur.fetchone()
            
            if not deleted:
                raise FileNotFoundError(f"Template '{template_name}' introuvable (doc_id: {doc_id})")
            
            conn.commit()
            
            print(f"🗑️ Template '{template_name}' supprimé (ID: {deleted[0]}, doc_id: {doc_id})")
            
            return f"database://templates/{deleted[0]}"
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Erreur suppression template: {e}")
            raise
        finally:
            cur.close()
            conn.close()