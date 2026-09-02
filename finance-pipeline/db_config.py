"""
Ortak Veritabanı Yapılandırması
Tüm servisler bu dosyadan DATABASE_URL'i alır.
"""
import os

# PostgreSQL Connection URL
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://admin:admin123@localhost:5432/finance_platform'
)

# Fallback: Eğer PostgreSQL erişilemezse SQLite'a dön
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')
SQLITE_URL = f'sqlite:///{SQLITE_PATH}'

def get_database_url():
    """Mevcut veritabanı URL'ini döndür. PostgreSQL tercih edilir."""
    url = DATABASE_URL
    if 'postgresql' in url:
        try:
            import psycopg2
            conn = psycopg2.connect(url.replace('postgresql://', '').split('@')[1].split('/')[0] if '@' in url else url)
            conn.close()
            return url
        except Exception:
            return SQLITE_URL
    return url

# Default export
DATABASE_URL_RESOLVED = get_database_url()
