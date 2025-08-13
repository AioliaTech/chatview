#!/usr/bin/env python3
"""
Sistema de visualização de conversas entre humano e IA
Para hospedar no EasyPanel - Com Sistema de Login
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json
from functools import wraps
import hashlib

app = Flask(__name__)

# Configuração da chave secreta para sessões
app.secret_key = os.getenv('SECRET_KEY', 'sua-chave-secreta-aqui')

# Configurações do banco de dados
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'seu_banco'),
    'user': os.getenv('DB_USER', 'seu_usuario'),
    'password': os.getenv('DB_PASSWORD', 'sua_senha'),
    'port': os.getenv('DB_PORT', '5432')
}

# Credenciais de login das variáveis de ambiente
LOGIN_USER = os.getenv('LOGIN_USER', 'admin')
LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD', 'senha123')

def hash_password(password):
    """Cria hash da senha para comparação segura"""
    return hashlib.sha256(password.encode()).hexdigest()

def require_auth(f):
    """Decorator que exige autenticação para acessar rotas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """Estabelece conexão com o PostgreSQL"""
    
    # Debug das variáveis de ambiente
    print("🔍 === DEBUG VARIÁVEIS DE AMBIENTE ===")
    print(f"DB_HOST: {os.getenv('DB_HOST', 'NÃO DEFINIDO')}")
    print(f"DB_NAME: {os.getenv('DB_NAME', 'NÃO DEFINIDO')}")
    print(f"DB_USER: {os.getenv('DB_USER', 'NÃO DEFINIDO')}")
    print(f"DB_PASSWORD: {'***DEFINIDO***' if os.getenv('DB_PASSWORD') else 'NÃO DEFINIDO'}")
    print(f"DB_PORT: {os.getenv('DB_PORT', 'NÃO DEFINIDO')}")
    print("🔍 =====================================")
    
    try:
        print(f"🔍 Tentando conectar com: {DATABASE_CONFIG['user']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}")
        conn = psycopg2.connect(**DATABASE_CONFIG)
        print("✅ Conexão com PostgreSQL estabelecida com sucesso!")
        return conn
    except psycopg2.Error as e:
        print(f"❌ Erro ao conectar com o banco: {e}")
        print(f"❌ Detalhes da conexão tentada: {DATABASE_CONFIG}")
        return None

def get_conversation_messages(session_id):
    """Busca todas as mensagens de uma conversa específica"""
    print(f"🔍 Buscando mensagens para session_id: {session_id}")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não conseguiu conectar ao banco")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query ajustada para sua estrutura atual
        query = """
        SELECT id, session_id, message
        FROM n8n_conversas 
        WHERE session_id = %s 
        ORDER BY id ASC
        """
        
        print(f"🔍 Executando query: {query}")
        print(f"🔍 Com parâmetro: {session_id}")
        
        cursor.execute(query, (session_id,))
        raw_messages = cursor.fetchall()
        
        print(f"🔍 Retornou {len(raw_messages)} mensagens do banco")
        
        # Processar mensagens JSON
        processed_messages = []
        for i, msg in enumerate(raw_messages):
            print(f"🔍 Processando mensagem {i+1}: ID={msg['id']}")
            try:
                # O campo message já vem como dict (JSONB), não precisa de json.loads()
                message_data = msg['message'] if isinstance(msg['message'], dict) else json.loads(msg['message'])
                print(f"🔍 Dados da mensagem: type={message_data.get('type')}, content_preview={str(message_data.get('content', ''))[:50]}...")
                
                processed_msg = {
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': message_data.get('content', ''),
                    'sender': message_data.get('type', 'unknown'),  # 'human' ou 'ai'
                    'timestamp': None,  # Você pode adicionar se tiver campo de timestamp
                    'raw_message': message_data  # Dados completos caso precise
                }
                processed_messages.append(processed_msg)
                
            except (json.JSONDecodeError, TypeError) as e:
                print(f"❌ Erro ao processar mensagem: {e}")
                # Se der erro, adiciona mensagem de erro
                processed_messages.append({
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': 'Erro ao processar mensagem',
                    'sender': 'system',
                    'timestamp': None,
                    'raw_message': {}
                })
        
        print(f"🎯 Retornando {len(processed_messages)} mensagens processadas")
        return processed_messages
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar mensagens: {e}")
        return []
    finally:
        conn.close()

def get_all_clients():
    """Busca todos os clientes únicos (parte antes do :)"""
    print("🔍 Buscando todos os clientes...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não conseguiu conectar ao banco")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT 
            SPLIT_PART(session_id, ':', 1) as client_name,
            COUNT(*) as total_conversations,
            COUNT(DISTINCT session_id) as unique_numbers,
            MAX(id) as last_id
        FROM n8n_conversas 
        WHERE session_id IS NOT NULL 
        AND session_id != ''
        AND session_id LIKE '%:%'
        GROUP BY SPLIT_PART(session_id, ':', 1)
        ORDER BY last_id DESC
        """
        
        print(f"🔍 Executando query de clientes: {query}")
        
        cursor.execute(query)
        clients = cursor.fetchall()
        
        print(f"🔍 Retornou {len(clients)} clientes do banco")
        for i, client in enumerate(clients[:5]):
            print(f"🔍 Cliente {i+1}: {client['client_name']} - {client['unique_numbers']} números")
        
        return [dict(client) for client in clients]
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar clientes: {e}")
        return []
    finally:
        conn.close()

def get_client_numbers(client_name):
    """Busca todos os números de um cliente específico"""
    print(f"🔍 Buscando números do cliente: {client_name}")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não conseguiu conectar ao banco")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT 
            session_id,
            SPLIT_PART(session_id, ':', 2) as phone_number,
            COUNT(*) as message_count,
            MAX(id) as last_id
        FROM n8n_conversas 
        WHERE session_id LIKE %s
        AND session_id IS NOT NULL 
        AND session_id != ''
        GROUP BY session_id
        ORDER BY last_id DESC
        """
        
        search_pattern = f"{client_name}:%"
        print(f"🔍 Buscando com pattern: {search_pattern}")
        
        cursor.execute(query, (search_pattern,))
        numbers = cursor.fetchall()
        
        print(f"🔍 Retornou {len(numbers)} números para {client_name}")
        
        return [dict(number) for number in numbers]
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar números: {e}")
        return []
    finally:
        conn.close()

def search_conversations(search_term):
    """Busca conversas por termo (cliente, número ou session_id completo)"""
    print(f"🔍 Buscando conversas com termo: {search_term}")
    
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT DISTINCT session_id, 
               COUNT(*) as message_count,
               MAX(id) as last_id,
               SPLIT_PART(session_id, ':', 1) as client_name,
               SPLIT_PART(session_id, ':', 2) as phone_number
        FROM n8n_conversas 
        WHERE session_id IS NOT NULL 
        AND session_id != ''
        AND (
            session_id ILIKE %s 
            OR SPLIT_PART(session_id, ':', 1) ILIKE %s
            OR SPLIT_PART(session_id, ':', 2) ILIKE %s
        )
        GROUP BY session_id 
        ORDER BY last_id DESC
        LIMIT 50
        """
        
        search_pattern = f"%{search_term}%"
        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        results = cursor.fetchall()
        
        print(f"🔍 Busca retornou {len(results)} resultados")
        
        return [dict(result) for result in results]
    
    except psycopg2.Error as e:
        print(f"❌ Erro na busca: {e}")
        return []
    finally:
        conn.close()

# === ROTAS DE AUTENTICAÇÃO ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login com debug"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # DEBUG - Vamos ver o que está chegando
        print("🔍 === DEBUG LOGIN ===")
        print(f"Username digitado: '{username}'")
        print(f"Password digitado: '{password}'")
        print(f"LOGIN_USER do ENV: '{LOGIN_USER}'")
        print(f"LOGIN_PASSWORD do ENV: '{LOGIN_PASSWORD}'")
        print(f"Username length: {len(username)}")
        print(f"Password length: {len(password)}")
        print(f"LOGIN_USER length: {len(LOGIN_USER)}")
        print(f"LOGIN_PASSWORD length: {len(LOGIN_PASSWORD)}")
        print(f"Username match: {username == LOGIN_USER}")
        print(f"Password match: {password == LOGIN_PASSWORD}")
        print(f"Username repr: {repr(username)}")
        print(f"Password repr: {repr(password)}")
        print(f"LOGIN_USER repr: {repr(LOGIN_USER)}")
        print(f"LOGIN_PASSWORD repr: {repr(LOGIN_PASSWORD)}")
        print("🔍 ==================")
        
        # Verificar credenciais
        if username == LOGIN_USER and password == LOGIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            print(f"✅ Login bem-sucedido para: {username}")
            return redirect(url_for('index'))
        else:
            print(f"❌ Tentativa de login falhada para: {username}")
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Fazer logout"""
    username = session.get('username', 'Usuário desconhecido')
    session.clear()
    print(f"✅ Logout realizado para: {username}")
    return redirect(url_for('login'))

@app.route('/debug-login')
def debug_login():
    """Debug das credenciais (REMOVER EM PRODUÇÃO!)"""
    return jsonify({
        "LOGIN_USER": LOGIN_USER,
        "LOGIN_PASSWORD": LOGIN_PASSWORD,  # Cuidado! Mostra a senha real
        "SECRET_KEY": app.secret_key,
        "env_vars": {
            "LOGIN_USER": os.getenv('LOGIN_USER', 'NOT SET'),
            "LOGIN_PASSWORD": os.getenv('LOGIN_PASSWORD', 'NOT SET'),
            "SECRET_KEY": os.getenv('SECRET_KEY', 'NOT SET')
        },
        "lengths": {
            "LOGIN_USER": len(LOGIN_USER),
            "LOGIN_PASSWORD": len(LOGIN_PASSWORD)
        }
    })

# === ROTAS PRINCIPAIS (PROTEGIDAS) ===

@app.route('/')
@require_auth
def index():
    """Página inicial com lista de clientes"""
    clients = get_all_clients()
    return render_template('clients.html', clients=clients)

@app.route('/client/<client_name>')
@require_auth
def view_client(client_name):
    """Visualiza números de um cliente específico"""
    numbers = get_client_numbers(client_name)
    return render_template('client_numbers.html', numbers=numbers, client_name=client_name)

@app.route('/chat/<session_id>')
@require_auth
def view_chat(session_id):
    """Visualiza uma conversa específica"""
    messages = get_conversation_messages(session_id)
    return render_template('chat.html', messages=messages, session_id=session_id)

@app.route('/search')
@require_auth
def search():
    """Busca universal - clientes, números ou conversas"""
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return redirect(url_for('index'))
    
    # Se o termo tem ':', é provável que seja session_id completo
    if ':' in search_term:
        messages = get_conversation_messages(search_term)
        if messages:
            return redirect(url_for('view_chat', session_id=search_term))
    
    # Senão, busca geral
    results = search_conversations(search_term)
    return render_template('search_results.html', results=results, search_term=search_term)

@app.route('/api/search')
@require_auth
def api_search():
    """API para busca em tempo real"""
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify([])
    
    results = search_conversations(search_term)
    return jsonify(results)

@app.route('/api/messages/<session_id>')
@require_auth
def api_messages(session_id):
    """API endpoint para buscar mensagens (útil para atualizações AJAX)"""
    messages = get_conversation_messages(session_id)
    return jsonify(messages)

# === ROTAS DE DEBUG (PROTEGIDAS) ===

@app.route('/debug')
@require_auth
def debug_info():
    """Endpoint para debug das configurações"""
    debug_data = {
        "environment_variables": {
            "DB_HOST": os.getenv('DB_HOST', 'NOT SET'),
            "DB_NAME": os.getenv('DB_NAME', 'NOT SET'),
            "DB_USER": os.getenv('DB_USER', 'NOT SET'),
            "DB_PASSWORD": "SET" if os.getenv('DB_PASSWORD') else "NOT SET",
            "DB_PORT": os.getenv('DB_PORT', 'NOT SET'),
            "LOGIN_USER": os.getenv('LOGIN_USER', 'NOT SET'),
            "LOGIN_PASSWORD": "SET" if os.getenv('LOGIN_PASSWORD') else "NOT SET",
            "SECRET_KEY": "SET" if os.getenv('SECRET_KEY') else "NOT SET"
        },
        "database_config": {
            "host": DATABASE_CONFIG['host'],
            "database": DATABASE_CONFIG['database'],
            "user": DATABASE_CONFIG['user'],
            "password": "***HIDDEN***",
            "port": DATABASE_CONFIG['port']
        },
        "current_user": session.get('username', 'Não logado')
    }
    
    # Testar conexão
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()[0]
            debug_data["database_test"] = "SUCCESS"
            debug_data["database_version"] = db_version
            conn.close()
        except Exception as e:
            debug_data["database_test"] = f"ERROR: {str(e)}"
    else:
        debug_data["database_test"] = "CONNECTION FAILED"
    
    return jsonify(debug_data)

@app.route('/find-tables')
@require_auth
def find_tables():
    """Endpoint para encontrar onde está a tabela n8n_conversas"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Conexão falhou"})
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Listar todos os bancos
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
        databases = [row['datname'] for row in cursor.fetchall()]
        
        # Listar todas as tabelas no banco atual
        cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """)
        tables = cursor.fetchall()
        
        # Buscar tabelas com "conversa" ou "n8n" no nome
        cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_name ILIKE '%conversa%' 
            OR table_name ILIKE '%n8n%'
            OR table_name ILIKE '%message%'
            OR table_name ILIKE '%chat%'
        """)
        relevant_tables = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "current_database": DATABASE_CONFIG['database'],
            "available_databases": databases,
            "all_tables_in_current_db": [dict(t) for t in tables],
            "relevant_tables": [dict(t) for t in relevant_tables]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/test-data')
@require_auth
def test_data():
    """Endpoint para testar dados reais da tabela"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Conexão falhou"})
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Teste 1: Total de registros
        cursor.execute("SELECT COUNT(*) as total FROM n8n_conversas")
        total = cursor.fetchone()['total']
        
        # Teste 2: Session_ids únicos
        cursor.execute("""
            SELECT session_id, COUNT(*) as count 
            FROM n8n_conversas 
            WHERE session_id IS NOT NULL 
            AND session_id != '' 
            GROUP BY session_id 
            ORDER BY count DESC 
            LIMIT 10
        """)
        sessions = cursor.fetchall()
        
        # Teste 3: Amostra de dados
        cursor.execute("SELECT id, session_id, message FROM n8n_conversas LIMIT 5")
        sample = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "total_records": total,
            "unique_sessions": [dict(s) for s in sessions],
            "sample_data": [dict(s) for s in sample]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/health')
def health_check():
    """Health check para o EasyPanel (não precisa de login)"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "healthy", "database": "connected"}
    else:
        return {"status": "unhealthy", "database": "disconnected"}, 500

if __name__ == '__main__':
    # Para desenvolvimento local
    app.run(debug=True, host='0.0.0.0', port=5000)
