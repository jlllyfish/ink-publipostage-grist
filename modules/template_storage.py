# -*- coding: utf-8 -*-
"""
Module de stockage des templates en base de données PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any
from datetime import datetime


class DatabaseTemplateStorage:
    """Gestion du stockage des templates dans PostgreSQL"""
    
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
        print("✅ Stockage PostgreSQL initialisé")
    
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
    
    def save_template(self, template_name: str, template_content: str, 
                      template_css: str = "", logo: str = None,
                      signature: str = None, service_name: str = None,
                      table_id: str = None) -> str:
        """
        Sauvegarde un template dans PostgreSQL
        
        Args:
            template_name: Nom du template
            template_content: Contenu HTML
            template_css: CSS personnalisé
            logo: Logo en base64
            signature: Signature en base64
            service_name: Nom du service
            table_id: ID de la table Grist associée
        
        Returns:
            Message de confirmation
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # Nettoyer le nom (identique à la version fichiers)
            safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            
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
                safe_name,
                template_content,
                template_css or '',
                logo,
                signature,
                service_name,
                table_id
            ))
            
            template_id = cur.fetchone()[0]
            conn.commit()
            
            print(f"✅ Template '{safe_name}' sauvegardé (ID: {template_id})")
            
            return f"database://templates/{template_id}"
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Erreur sauvegarde template: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """
        Charge un template depuis PostgreSQL
        
        Args:
            template_name: Nom du template
        
        Returns:
            Dictionnaire avec les données du template
        
        Raises:
            FileNotFoundError: Si le template n'existe pas
        """
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Nettoyer le nom
            safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            
            cur.execute("""
                SELECT content, css, logo, signature, service_name, table_id
                FROM templates 
                WHERE name = %s
            """, (safe_name,))
            
            row = cur.fetchone()
            
            if not row:
                raise FileNotFoundError(f"Template '{template_name}' introuvable")
            
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
    
    def list_templates(self) -> List[str]:
        """
        Liste tous les templates disponibles
        
        Returns:
            Liste des noms de templates (triés par date de modification)
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT name 
                FROM templates 
                ORDER BY updated_at DESC
            """)
            
            templates = [row[0] for row in cur.fetchall()]
            return templates
            
        finally:
            cur.close()
            conn.close()
    
    def delete_template(self, template_name: str) -> str:
        """
        Supprime un template
        
        Args:
            template_name: Nom du template à supprimer
        
        Returns:
            Message de confirmation
        
        Raises:
            FileNotFoundError: Si le template n'existe pas
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # Nettoyer le nom
            safe_name = "".join(c for c in template_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            
            cur.execute("""
                DELETE FROM templates 
                WHERE name = %s
                RETURNING id
            """, (safe_name,))
            
            deleted = cur.fetchone()
            
            if not deleted:
                raise FileNotFoundError(f"Template '{template_name}' introuvable")
            
            conn.commit()
            
            print(f"🗑️ Template '{safe_name}' supprimé (ID: {deleted[0]})")
            
            return f"database://templates/{deleted[0]}"
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Erreur suppression template: {e}")
            raise
        finally:
            cur.close()
            conn.close()