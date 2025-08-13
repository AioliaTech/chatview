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
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"❌ Erro ao conectar com o banco: {e}")
        return None

def get_conversation_messages(session_id):
    """Busca todas as mensagens de uma conversa específica"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT id, session_id, message
        FROM n8n_conversas 
        WHERE session_id = %s 
        ORDER BY id ASC
        """
        
        cursor.execute(query, (session_id,))
        raw_messages = cursor.fetchall()
        
        # Processar mensagens JSON
        processed_messages = []
        for msg in raw_messages:
            try:
                # O campo message já vem como dict (JSONB)
                message_data = msg['message'] if isinstance(msg['message'], dict) else json.loads(msg['message'])
                
                processed_msg = {
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': message_data.get('content', ''),
                    'sender': message_data.get('type', 'unknown'),
                    'timestamp': None,
                    'raw_message': message_data
                }
                processed_messages.append(processed_msg)
                
            except (json.JSONDecodeError, TypeError):
                processed_messages.append({
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': 'Erro ao processar mensagem',
                    'sender': 'system',
                    'timestamp': None,
                    'raw_message': {}
                })
        
        return processed_messages
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar mensagens: {e}")
        return []
    finally:
        conn.close()

def get_all_clients():
    """Busca todos os clientes únicos (parte antes do :)"""
    conn = get_db_connection()
    if not conn:
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
        
        cursor.execute(query)
        clients = cursor.fetchall()
        
        return [dict(client) for client in clients]
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar clientes: {e}")
        return []
    finally:
        conn.close()

def get_client_numbers(client_name):
    """Busca todos os números de um cliente específico"""
    conn = get_db_connection()
    if not conn:
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
        cursor.execute(query, (search_pattern,))
        numbers = cursor.fetchall()
        
        return [dict(number) for number in numbers]
    
    except psycopg2.Error as e:
        print(f"❌ Erro ao buscar números: {e}")
        return []
    finally:
        conn.close()

def search_conversations(search_term):
    """Busca conversas por termo (cliente, número ou session_id completo)"""
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
        
        return [dict(result) for result in results]
    
    except psycopg2.Error as e:
        print(f"❌ Erro na busca: {e}")
        return []
    finally:
        conn.close()

# === ROTAS DE AUTENTICAÇÃO ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == LOGIN_USER and password == LOGIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Fazer logout"""
    session.clear()
    return redirect(url_for('login'))

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
    
    if ':' in search_term:
        messages = get_conversation_messages(search_term)
        if messages:
            return redirect(url_for('view_chat', session_id=search_term))
    
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
    """API endpoint para buscar mensagens"""
    messages = get_conversation_messages(session_id)
    return jsonify(messages)

@app.route('/health')
def health_check():
    """Health check para o EasyPanel"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "healthy", "database": "connected"}
    else:
        return {"status": "unhealthy", "database": "disconnected"}, 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
