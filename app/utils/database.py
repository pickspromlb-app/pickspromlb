"""
PicksProMLB - Cliente de Supabase
Conexión centralizada a la base de datos
"""

from supabase import create_client, Client
from loguru import logger
from app.utils.config import config


class SupabaseClient:
    """Cliente singleton para conectarse a Supabase"""
    
    _instance = None
    _client: Client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self) -> Client:
        """Retorna el cliente de Supabase, creándolo si no existe"""
        if self._client is None:
            try:
                self._client = create_client(
                    config.SUPABASE_URL,
                    config.SUPABASE_KEY
                )
                logger.info("✅ Conectado a Supabase")
            except Exception as e:
                logger.error(f"❌ Error conectando a Supabase: {e}")
                raise
        return self._client
    
    def insert(self, table: str, data: dict | list) -> dict:
        """Inserta uno o varios registros en una tabla"""
        client = self.get_client()
        try:
            response = client.table(table).insert(data).execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error insertando en {table}: {e}")
            raise
    
    def upsert(self, table: str, data: dict | list, on_conflict: str = None) -> dict:
        """Inserta o actualiza registros"""
        client = self.get_client()
        try:
            query = client.table(table).upsert(data)
            if on_conflict:
                query = query.upsert(data, on_conflict=on_conflict)
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error en upsert {table}: {e}")
            raise
    
    def select(self, table: str, columns: str = "*", filters: dict = None) -> list:
        """Selecciona registros con filtros opcionales"""
        client = self.get_client()
        try:
            query = client.table(table).select(columns)
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error consultando {table}: {e}")
            raise
    
    def update(self, table: str, data: dict, filters: dict) -> dict:
        """Actualiza registros que coincidan con los filtros"""
        client = self.get_client()
        try:
            query = client.table(table).update(data)
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error actualizando {table}: {e}")
            raise
    
    def delete(self, table: str, filters: dict) -> dict:
        """Elimina registros que coincidan con los filtros"""
        client = self.get_client()
        try:
            query = client.table(table).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error eliminando de {table}: {e}")
            raise
    
    def call_rpc(self, function_name: str, params: dict = None) -> dict:
        """Llama a una función SQL almacenada en Supabase"""
        client = self.get_client()
        try:
            response = client.rpc(function_name, params or {}).execute()
            return response.data
        except Exception as e:
            logger.error(f"❌ Error llamando RPC {function_name}: {e}")
            raise


# Instancia global para usar en todo el proyecto
db = SupabaseClient()
