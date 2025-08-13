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
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar com o banco: {e}")
        return None

def get_conversation_messages(session_id):
    """Busca todas as mensagens de uma conversa específica"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query ajustada para sua estrutura atual
        query = """
        SELECT id, session_id, message
        FROM sua_tabela_aqui 
        WHERE session_id = %s 
        ORDER BY id ASC
        """
        
        cursor.execute(query, (session_id,))
        raw_messages = cursor.fetchall()
        
        # Processar mensagens JSON
        processed_messages = []
        for msg in raw_messages:
            try:
                # Parse do JSON da mensagem
                message_data = json.loads(msg['message'])
                
                processed_msg = {
                    'id': msg['id'],
                    'session_id': msg['session_id'],
                    'message': message_data.get('content', ''),
                    'sender': message_data.get('type', 'unknown'),  # 'human' ou 'ai'
                    'timestamp': None,  # Você pode adicionar se tiver campo de timestamp
                    'raw_message': message_data  # Dados completos caso precise
                }
                processed_messages.append(processed_msg)
                
            except json.JSONDecodeError:
                # Se der erro no JSON, adiciona mensagem de erro
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
        print(f"Erro ao buscar mensagens: {e}")
        return []
    finally:
        conn.close()

def get_all_conversations():
    """Busca todas as conversas disponíveis (session_ids únicos)"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT DISTINCT session_id, 
               COUNT(*) as message_count,
               MAX(id) as last_id
        FROM sua_tabela_aqui 
        GROUP BY session_id 
        ORDER BY last_id DESC
        """
        
        cursor.execute(query)
        conversations = cursor.fetchall()
        
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
