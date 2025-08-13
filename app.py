#!/usr/bin/env python3
"""
Sistema de visualização de conversas entre humano e IA
Para hospedar no EasyPanel
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json

app = Flask(__name__)

# Configurações do banco de dados
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'seu_banco'),
    'user': os.getenv('DB_USER', 'seu_usuario'),
    'password': os.getenv('DB_PASSWORD', 'sua_senha'),
    'port': os.getenv('DB_PORT', '5432')
}

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
                # Parse do JSON da mensagem
                message_data = json.loads(msg['message'])
                print(f"🔍 JSON parsed: type={message_data.get('type')}, content_preview={str(message_data.get('content', ''))[:50]}...")
                
                processed_msg = {
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': message_data.get('content', ''),
                    'sender': message_data.get('type', 'unknown'),  # 'human' ou 'ai'
                    'timestamp': None,  # Você pode adicionar se tiver campo de timestamp
                    'raw_message': message_data  # Dados completos caso precise
                }
                processed_messages.append(processed_msg)
                
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao fazer parse do JSON: {e}")
                # Se der erro no JSON, adiciona mensagem de erro
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
        print(f"Erro ao buscar mensagens: {e}")
        return []
    finally:
        conn.close()

def get_all_conversations():
    """Busca todas as conversas disponíveis (session_ids únicos)"""
    print("🔍 Buscando todas as conversas...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Erro: Não conseguiu conectar ao banco")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT DISTINCT session_id, 
               COUNT(*) as message_count,
               MAX(id) as last_id
        FROM n8n_conversas 
        WHERE session_id IS NOT NULL 
        AND session_id != ''
        GROUP BY session_id 
        ORDER BY last_id DESC
        LIMIT 50
        """
        
        print(f"🔍 Executando query: {query}")
        
        cursor.execute(query)
        conversations = cursor.fetchall()
        
        print(f"🔍 Retornou {len(conversations)} conversas do banco")
        for i, conv in enumerate(conversations[:3]):
            print(f"🔍 Conversa {i+1}: session_id={conv['session_id']}, mensagens={conv['message_count']}")
        
        return [dict(conv) for conv in conversations]
    
    except psycopg2.Error as e:
        print(f"Erro ao buscar conversas: {e}")
        return []
    finally:
        conn.close()

@app.route('/')
def index():
    """Página inicial com lista de conversas"""
    conversations = get_all_conversations()
    return render_template('index.html', conversations=conversations)

@app.route('/chat/<session_id>')
def view_chat(session_id):
    """Visualiza uma conversa específica"""
    messages = get_conversation_messages(session_id)
    return render_template('chat.html', messages=messages, session_id=session_id)

@app.route('/search')
def search():
    """Busca conversa por session_id específico"""
    session_id = request.args.get('key', '').strip()
    if session_id:
        messages = get_conversation_messages(session_id)
        if messages:
            return redirect(url_for('view_chat', session_id=session_id))
        else:
            return render_template('index.html', 
                                 conversations=get_all_conversations(),
                                 error=f"Nenhuma conversa encontrada para o session_id: {session_id}")
    
    return redirect(url_for('index'))

@app.route('/api/messages/<session_id>')
def api_messages(session_id):
    """API endpoint para buscar mensagens (útil para atualizações AJAX)"""
    messages = get_conversation_messages(session_id)
    return jsonify(messages)

@app.route('/find-tables')
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
        
        # Teste 4: Busca específica
        cursor.execute("SELECT COUNT(*) as found FROM n8n_conversas WHERE session_id = %s", ('franca:554899542122',))
        specific_search = cursor.fetchone()['found']
        
        conn.close()
        
        return jsonify({
            "total_records": total,
            "unique_sessions": [dict(s) for s in sessions],
            "sample_data": [dict(s) for s in sample],
            "specific_search_franca": specific_search
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/debug')
def debug_info():
    """Endpoint para debug das configurações"""
    debug_data = {
        "environment_variables": {
            "DB_HOST": os.getenv('DB_HOST', 'NOT SET'),
            "DB_NAME": os.getenv('DB_NAME', 'NOT SET'),
            "DB_USER": os.getenv('DB_USER', 'NOT SET'),
            "DB_PASSWORD": "SET" if os.getenv('DB_PASSWORD') else "NOT SET",
            "DB_PORT": os.getenv('DB_PORT', 'NOT SET')
        },
        "database_config": {
            "host": DATABASE_CONFIG['host'],
            "database": DATABASE_CONFIG['database'],
            "user": DATABASE_CONFIG['user'],
            "password": "***HIDDEN***",
            "port": DATABASE_CONFIG['port']
        }
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
    # Para desenvolvimento local
    app.run(debug=True, host='0.0.0.0', port=5000)
