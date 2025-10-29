from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
import pandas as pd
import networkx as nx
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import numpy as np

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Crear directorio de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Datos globales
current_data = None
current_filename = None

def load_last_data():
    """Carga los datos del último archivo subido"""
    global current_data, current_filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'current.csv')
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            current_data = df
            current_filename = 'current.csv'
            print(f"Datos cargados automáticamente: {len(df)} filas")
        except Exception as e:
            print(f"Error cargando datos guardados: {e}")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_csv_columns(df):
    required_columns = [
        'Entidad', 'Sistema de origen', 'Sistema de Destino', 
        'Tipo de Transmisión', 'Propietario Datos de Destino', 'Riesgo de falla'
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    return len(missing_columns) == 0, missing_columns

def clean_dataframe(df):
    """Limpia el DataFrame manejando valores vacíos y nulos"""
    df_clean = df.copy()
    
    # Reemplazar diferentes representaciones de valores vacíos
    empty_values = ['', ' ', 'N/A', 'n/a', 'NULL', 'null', 'NaN', 'nan', None, np.nan]
    
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            df_clean[col] = df_clean[col].replace(empty_values, 'No especificado')
        else:
            df_clean[col] = df_clean[col].replace(empty_values, 0)
    
    return df_clean

def risk_to_numeric(risk):
    risk_map = {'Alto': 3, 'Medio': 2, 'Bajo': 1, 'No especificado': 1}
    return risk_map.get(risk, 1)

def generate_graph_from_row(row_data):
    G = nx.DiGraph()
    
    # Obtener valores con manejo de nulos
    entidad = row_data.get('Entidad', 'Entidad desconocida')
    sistema_origen = row_data.get('Sistema de origen', 'Sistema origen desconocido')
    sistema_destino = row_data.get('Sistema de Destino', 'Sistema destino desconocido')
    tipo_transmision = row_data.get('Tipo de Transmisión', 'No especificado')
    propietario = row_data.get('Propietario Datos de Destino', 'No especificado')
    riesgo = row_data.get('Riesgo de falla', 'No especificado')
    
    # Agregar nodos (asegurarse de que no estén vacíos)
    if entidad and entidad != 'No especificado':
        G.add_node(entidad, tipo='Entidad')
    if sistema_origen and sistema_origen != 'No especificado':
        G.add_node(sistema_origen, tipo='Sistema')
    if sistema_destino and sistema_destino != 'No especificado':
        G.add_node(sistema_destino, tipo='Sistema')
    
    # Agregar aristas solo si los nodos existen
    if (entidad and entidad != 'No especificado' and 
        sistema_origen and sistema_origen != 'No especificado'):
        G.add_edge(
            entidad, 
            sistema_origen,
            tipo='envío',
            tipo_transmision=tipo_transmision,
            propietario=propietario,
            riesgo=riesgo,
            riesgo_numerico=risk_to_numeric(riesgo)
        )
    
    if (sistema_origen and sistema_origen != 'No especificado' and 
        sistema_destino and sistema_destino != 'No especificado'):
        G.add_edge(
            sistema_origen, 
            sistema_destino,
            tipo='transferencia',
            tipo_transmision=tipo_transmision,
            propietario=propietario,
            riesgo=riesgo,
            riesgo_numerico=risk_to_numeric(riesgo)
        )
    
    return G

def graph_to_cytoscape(G):
    nodes = []
    edges = []
    
    # Calcular grados para tamaño de nodos
    degrees = dict(G.degree())
    max_degree = max(degrees.values()) if degrees else 1
    
    for node in G.nodes():
        node_data = {
            'data': {
                'id': str(node),
                'tipo': str(G.nodes[node].get('tipo', 'Desconocido')),
                'grado': int(degrees.get(node, 1)),
                'tamaño': float(30 + (degrees.get(node, 1) / max_degree) * 50)
            }
        }
        nodes.append(node_data)
    
    for edge in G.edges(data=True):
        source, target, data = edge
        edge_data = {
            'data': {
                'id': f"{source}-{target}",
                'source': str(source),
                'target': str(target),
                'tipo': str(data.get('tipo', '')),
                'tipo_transmision': str(data.get('tipo_transmision', '')),
                'propietario': str(data.get('propietario', '')),
                'riesgo': str(data.get('riesgo', '')),
                'riesgo_numerico': int(data.get('riesgo_numerico', 1)),
                'peso': int(data.get('riesgo_numerico', 1))
            }
        }
        edges.append(edge_data)
    
    return nodes + edges

# Cargar datos automáticamente al iniciar
load_last_data()

# Rutas de Navegación Principal
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/table')
def table_page():
    # Pasar datos iniciales a la plantilla para evitar el problema de timing
    data_info = {
        'loaded': current_data is not None,
        'filename': current_filename,
        'total_rows': len(current_data) if current_data is not None else 0
    }
    return render_template('table.html', data_info=data_info)

@app.route('/graph')
def graph_page():
    row_id = request.args.get('row_id')
    return render_template('graph.html', row_id=row_id)

# API Endpoints
@app.route('/api/upload', methods=['POST'])
def upload_file():
    global current_data, current_filename
    
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se proporcionó archivo'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Leer CSV con manejo de valores vacíos
                df = pd.read_csv(
                    filepath, 
                    na_values=['', ' ', 'N/A', 'n/a', 'NULL', 'null', 'NaN', 'nan'],
                    keep_default_na=True
                )
                
                # Validar columnas
                is_valid, missing_columns = validate_csv_columns(df)
                
                if not is_valid:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return jsonify({
                        'error': f'Columnas obligatorias faltantes: {", ".join(missing_columns)}'
                    }), 400
                
                # Limpiar datos
                df_clean = clean_dataframe(df)
                
                # Agregar ID único a cada fila
                df_clean['id'] = range(1, len(df_clean) + 1)
                
                # Guardar copia limpia para persistencia
                df_clean.to_csv(os.path.join(app.config['UPLOAD_FOLDER'], 'current.csv'), index=False)
                
                # ACTUALIZAR INMEDIATAMENTE las variables globales
                current_data = df_clean
                current_filename = filename
                
                print(f"Datos cargados exitosamente: {len(df_clean)} filas")
                
                # En lugar de redirect, devolver los datos inmediatamente
                return jsonify({
                    'success': True,
                    'message': 'Archivo cargado y procesado exitosamente',
                    'rows': len(df_clean),
                    'columns': len(df_clean.columns),
                    'data_preview': df_clean.head(10).to_dict('records'),  # Enviar preview
                    'redirect': url_for('table_page')
                })
                
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                print(f"Error procesando CSV: {str(e)}")
                return jsonify({'error': f'Error procesando CSV: {str(e)}'}), 400
        
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
        
    except Exception as e:
        print(f"Error interno: {str(e)}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/table', methods=['GET'])
def get_table_data():
    global current_data
    
    # Cargar datos si no están en memoria
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({
                'data': [], 
                'total': 0, 
                'page': 1, 
                'size': 25, 
                'total_pages': 0
            })
    
    try:
        # Parámetros de paginación y filtros
        page = request.args.get('page', 1, type=int)
        size = request.args.get('size', 25, type=int)
        sort_col = request.args.get('sort', 'id')
        sort_dir = request.args.get('sort_dir', 'asc')
        search = request.args.get('search', '')
        
        # Filtros adicionales
        entity_filter = request.args.get('entity', '')
        system_filter = request.args.get('system', '')
        type_filter = request.args.get('type', '')
        risk_filter = request.args.get('risk', '')
        
        # Copiar datos limpios
        filtered_data = current_data.copy()
        
        # Aplicar búsqueda
        if search and search.strip():
            mask = filtered_data.astype(str).apply(
                lambda x: x.str.contains(search, case=False, na=False)
            ).any(axis=1)
            filtered_data = filtered_data[mask]
        
        # Aplicar filtros
        if entity_filter:
            if entity_filter == 'No especificado':
                filtered_data = filtered_data[filtered_data['Entidad'] == 'No especificado']
            else:
                filtered_data = filtered_data[filtered_data['Entidad'] == entity_filter]
                
        if system_filter:
            if system_filter == 'No especificado':
                mask = (filtered_data['Sistema de origen'] == 'No especificado') | \
                       (filtered_data['Sistema de Destino'] == 'No especificado')
            else:
                mask = (filtered_data['Sistema de origen'] == system_filter) | \
                       (filtered_data['Sistema de Destino'] == system_filter)
            filtered_data = filtered_data[mask]
            
        if type_filter:
            if type_filter == 'No especificado':
                filtered_data = filtered_data[filtered_data['Tipo de Transmisión'] == 'No especificado']
            else:
                filtered_data = filtered_data[filtered_data['Tipo de Transmisión'] == type_filter]
                
        if risk_filter:
            if risk_filter == 'No especificado':
                filtered_data = filtered_data[filtered_data['Riesgo de falla'] == 'No especificado']
            else:
                filtered_data = filtered_data[filtered_data['Riesgo de falla'] == risk_filter]
        
        # Aplicar ordenamiento
        if sort_col in filtered_data.columns:
            filtered_data = filtered_data.sort_values(
                by=sort_col, 
                ascending=(sort_dir == 'asc'),
                na_position='last'
            )
        
        # Aplicar paginación
        total_rows = len(filtered_data)
        total_pages = max(1, (total_rows + size - 1) // size) if size > 0 else 1
        
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_data = filtered_data.iloc[start_idx:end_idx]
        
        # Convertir a formato JSON seguro
        data_records = []
        for _, row in paginated_data.iterrows():
            record = {}
            for col in paginated_data.columns:
                value = row[col]
                # Convertir a tipos nativos de Python
                if pd.isna(value):
                    record[col] = None
                elif hasattr(value, 'item'):  # Para numpy types
                    record[col] = value.item() if hasattr(value, 'item') else value
                else:
                    record[col] = value
            data_records.append(record)
        
        return jsonify({
            'data': data_records,
            'total': int(total_rows),
            'page': int(page),
            'size': int(size),
            'total_pages': int(total_pages)
        })
        
    except Exception as e:
        print(f"Error en /api/table: {str(e)}")
        return jsonify({'error': f'Error procesando datos: {str(e)}'}), 500

@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    global current_data
    
    # Cargar datos si no están en memoria
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({
                'entities': [], 
                'systems': [], 
                'types': [], 
                'risks': []
            })
    
    try:
        # Obtener opciones únicas
        entities = current_data['Entidad'].unique().tolist()
        systems_orig = current_data['Sistema de origen'].unique().tolist()
        systems_dest = current_data['Sistema de Destino'].unique().tolist()
        systems = list(set(systems_orig + systems_dest))
        types = current_data['Tipo de Transmisión'].unique().tolist()
        risks = current_data['Riesgo de falla'].unique().tolist()
        
        # Limpiar y ordenar
        entities_clean = sorted([str(e) for e in entities if e and str(e) != 'nan'])
        systems_clean = sorted([str(s) for s in systems if s and str(s) != 'nan'])
        types_clean = sorted([str(t) for t in types if t and str(t) != 'nan'])
        risks_clean = sorted([str(r) for r in risks if r and str(r) != 'nan'])
        
        return jsonify({
            'entities': entities_clean,
            'systems': systems_clean,
            'types': types_clean,
            'risks': risks_clean
        })
    except Exception as e:
        print(f"Error en /api/filter-options: {str(e)}")
        return jsonify({'error': f'Error obteniendo opciones: {str(e)}'}), 500

@app.route('/api/graph', methods=['GET'])
def get_graph():
    global current_data
    
    # Cargar datos si no están en memoria
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'error': 'No hay datos cargados'}), 400
    
    try:
        row_id = request.args.get('row_id', type=int)
        
        if not row_id:
            return jsonify({'error': 'ID de fila no proporcionado'}), 400
        
        # Buscar la fila específica
        row_data = current_data[current_data['id'] == row_id]
        
        if row_data.empty:
            return jsonify({'error': f'Fila con ID {row_id} no encontrada'}), 404
        
        row_dict = row_data.iloc[0].to_dict()
        
        # Generar grafo
        G = generate_graph_from_row(row_dict)
        elements = graph_to_cytoscape(G)
        
        return jsonify({
            'elements': elements,
            'row_data': row_dict
        })
    except Exception as e:
        print(f"Error en /api/graph: {str(e)}")
        return jsonify({'error': f'Error generando grafo: {str(e)}'}), 500

@app.route('/api/data-info', methods=['GET'])
def get_data_info():
    """Endpoint para obtener información sobre los datos cargados"""
    global current_data
    
    # Cargar datos si no están en memoria
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'loaded': False})
    
    try:
        # Estadísticas de datos vacíos
        empty_stats = {}
        for col in current_data.columns:
            empty_count = current_data[col].isnull().sum()
            total_count = len(current_data)
            empty_stats[col] = {
                'empty_count': int(empty_count),
                'empty_percentage': float(round((empty_count / total_count) * 100, 2)) if total_count > 0 else 0.0
            }
        
        return jsonify({
            'loaded': True,
            'filename': current_filename,
            'total_rows': int(len(current_data)),
            'total_columns': int(len(current_data.columns)),
            'empty_stats': empty_stats,
            'columns': list(current_data.columns)
        })
    except Exception as e:
        return jsonify({'error': f'Error obteniendo información: {str(e)}'}), 500

@app.route('/api/download', methods=['GET'])
def download_file():
    global current_data
    
    # Cargar datos si no están en memoria
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'error': 'No hay datos para descargar'}), 400
    
    try:
        download_filename = f"transmisiones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], download_filename)
        
        # Remover la columna ID temporal antes de descargar
        download_data = current_data.drop('id', axis=1, errors='ignore')
        download_data.to_csv(filepath, index=False)
        
        return send_file(filepath, as_attachment=True, download_name=download_filename)
        
    except Exception as e:
        return jsonify({'error': f'Error descargando archivo: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)