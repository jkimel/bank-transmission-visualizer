from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_cors import CORS
import pandas as pd
import networkx as nx
import os
import json
import re
from datetime import datetime
from werkzeug.utils import secure_filename
import numpy as np

app = Flask(__name__)
CORS(app)
app.secret_key = '1234'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Crear directorio de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Datos globales
current_data = None
current_filename = None

def load_last_data():
    """Carga los datos del último archivo subido (sin romper si no existe)"""
    global current_data, current_filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'current.csv')

    if not os.path.exists(filepath):
        print("⚠️ No se encontró 'current.csv', se inicia sin datos.")
        current_data = None
        current_filename = None
        return

    try:
        df = pd.read_csv(filepath)
        current_data = df
        current_filename = 'current.csv'
        print(f"Datos cargados automáticamente: {len(df)} filas")
    except Exception as e:
        print(f"⚠️ Error cargando datos guardados: {e}")
        current_data = None
        current_filename = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_csv_columns(df):
    """Valida que el CSV tenga las columnas mínimas requeridas: Origen, Destino, Latencia_ms."""
    required_columns = ['Origen', 'Destino', 'Latencia_ms']
    
    column_mappings = {}
    missing_columns = []
    
    for required_col in required_columns:
        found = False
        for actual_col in df.columns:
            # Buscar coincidencia (insensible a mayúsculas y espacios)
            if required_col.lower().replace('_', '').replace(' ', '') == actual_col.lower().replace('_', '').replace(' ', ''):
                column_mappings[required_col] = actual_col
                found = True
                break
        
        if not found:
            missing_columns.append(required_col)
    
    # Si todas las columnas requeridas fueron encontradas y mapeadas:
    if len(missing_columns) == 0:
        df_clean = df.rename(columns=column_mappings)
        
        # Convertir Latencia a numérico, ignorando errores
        df_clean['Latencia_ms'] = pd.to_numeric(df_clean['Latencia_ms'], errors='coerce')
        
        # Eliminar filas con valores nulos o latencias negativas (Dijkstra requiere pesos no negativos)
        df_clean.dropna(subset=['Origen', 'Destino', 'Latencia_ms'], inplace=True)
        df_clean = df_clean[df_clean['Latencia_ms'] >= 0]
        
        df_clean['id'] = range(1, len(df_clean) + 1)
        
        return True, df_clean, column_mappings
    
    return False, None, missing_columns

def clean_and_standardize_dataframe(df, column_mappings):
    is_valid, df_clean, missing_cols = validate_csv_columns(df)
    
    if not is_valid:
        raise ValueError(f"Faltan columnas obligatorias: {', '.join(missing_cols)}")

    # Asegurar que los nombres y el orden sean los esperados
    df_clean = df_clean[['id', 'Origen', 'Destino', 'Latencia_ms']]
    
    return df_clean

def generate_full_latency_graph():
    """Genera el grafo dirigido y ponderado con todos los datos de latencia."""
    global current_data
    if current_data is None:
        return nx.DiGraph()

    G = nx.DiGraph()
    
    for _, row in current_data.iterrows():
        origen = str(row['Origen'])
        destino = str(row['Destino'])
        latencia = row['Latencia_ms']
        
        G.add_edge(
            origen, 
            destino, 
            weight=latencia,
            label=f"{latencia:.1f} ms"
        )
        
    return G

# --- Rutas de Navegación Principal ---
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
    # La página de grafo ya no necesita row_id, siempre muestra el grafo completo
    return render_template('graph.html')

# --- API Endpoints ---
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
                df = pd.read_csv(
                    filepath, 
                    na_values=['', ' ', 'N/A', 'n/a', 'NULL', 'null', 'NaN', 'nan'],
                    keep_default_na=True
                )
                
                is_valid, df_clean_temp, column_mappings = validate_csv_columns(df)
                
                if not is_valid:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return jsonify({
                        'error': f'Columnas obligatorias faltantes: {", ".join(column_mappings)}'
                    }), 400
                
                df_clean = clean_and_standardize_dataframe(df, column_mappings)
                
                # Guardar copia limpia para persistencia
                df_clean.to_csv(os.path.join(app.config['UPLOAD_FOLDER'], 'current.csv'), index=False)
                
                # ACTUALIZAR INMEDIATAMENTE las variables globales
                current_data = df_clean
                current_filename = filename
                
                return jsonify({
                    'success': True,
                    'message': 'Archivo cargado y procesado exitosamente',
                    'rows': len(df_clean),
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
    
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({
                'data': [], 
                'total': 0, 
                'page': 1, 
                'size': 25, 
                'total_pages': 0,
                'columns': ['id', 'Origen', 'Destino', 'Latencia_ms']
            })
    
    try:
        page = request.args.get('page', 1, type=int)
        size = request.args.get('size', 25, type=int)
        sort_col = request.args.get('sort', 'id')
        sort_dir = request.args.get('sort_dir', 'asc')
        search = request.args.get('search', '')
        
        # Filtros específicos (para el futuro si se agregan)
        filter_origen = request.args.get('origen', '')
        filter_destino = request.args.get('destino', '')
        
        filtered_data = current_data.copy()
        
        # Aplicar filtros específicos
        if filter_origen:
            filtered_data = filtered_data[filtered_data['Origen'].astype(str) == filter_origen]
        if filter_destino:
            filtered_data = filtered_data[filtered_data['Destino'].astype(str) == filter_destino]
        
        # Aplicar búsqueda general
        if search and search.strip():
            mask = filtered_data.astype(str).apply(
                lambda x: x.str.contains(search, case=False, na=False)
            ).any(axis=1)
            filtered_data = filtered_data[mask]
        
        # Aplicar ordenamiento
        if sort_col in filtered_data.columns:
            
            # Función auxiliar para Ordenamiento Natural (Natural Sort)
            # Convierte "R10" en ['r', 10] y "R2" en ['r', 2] para que el 2 gane.
            def natural_keys(text):
                return [int(c) if c.isdigit() else c.lower() 
                        for c in re.split(r'(\d+)', str(text))]
            
            # Truco de Pandas:
            # 1. Creamos una columna temporal invisible con la "clave natural"
            filtered_data['_sort_temp'] = filtered_data[sort_col].apply(natural_keys)
            
            # 2. Ordenamos usando esa columna temporal
            filtered_data = filtered_data.sort_values(
                by='_sort_temp', 
                ascending=(sort_dir == 'asc')
            )
            
            # 3. Borramos la columna temporal para que no salga en el JSON
            filtered_data = filtered_data.drop(columns=['_sort_temp'])
        
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
            for col in ['id', 'Origen', 'Destino', 'Latencia_ms']:
                value = row[col]
                if pd.isna(value):
                    record[col] = None
                elif hasattr(value, 'item'):
                    record[col] = value.item() if hasattr(value, 'item') else value
                else:
                    record[col] = value
            data_records.append(record)
        
        original_columns = ['id', 'Origen', 'Destino', 'Latencia_ms']
        
        return jsonify({
            'data': data_records,
            'total': int(total_rows),
            'page': int(page),
            'size': int(size),
            'total_pages': int(total_pages),
            'columns': original_columns
        })
        
    except Exception as e:
        print(f"Error en /api/table: {str(e)}")
        return jsonify({'error': f'Error procesando datos: {str(e)}'}), 500
    
@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    global current_data
    
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({ 'origenes': [], 'destinos': [] })
        
    try:
        origenes = current_data['Origen'].unique().tolist()
        destinos = current_data['Destino'].unique().tolist()
        
        origen_clean = sorted([str(s) for s in origenes if s and str(s) != 'nan'])
        destino_clean = sorted([str(t) for t in destinos if t and str(t) != 'nan'])
        
        # DEVOLVER SOLO LAS CLAVES NECESARIAS
        return jsonify({
            'origenes': origen_clean,
            'destinos': destino_clean
        })
    except Exception as e:
        print(f"Error en /api/filter-options: {str(e)}")
        return jsonify({'error': f'Error obteniendo opciones: {str(e)}'}), 500

@app.route('/api/graph', methods=['GET'])
def get_full_graph():
    global current_data

    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'error': 'No hay datos cargados'}), 400

    try:
        G = generate_full_latency_graph()

        nodes_data = [{'id': n, 'label': n, 'title': n} for n in G.nodes()]
        
        edges_data = []
        for u, v, data in G.edges(data=True):
            edges_data.append({
                'from': u,
                'to': v,
                'weight': data['weight'],
                'label': data['label'],
                'title': f"Latencia: {data['weight']:.1f} ms",
                'id': f"{u}-{v}-{data['weight']}"
            })

        return jsonify({
            'nodes': nodes_data,
            'edges': edges_data,
            'nodos': len(G.nodes()),
            'aristas': len(G.edges()),
            'all_nodes': sorted(list(G.nodes()))
        })

    except Exception as e:
        print(f"Error en /api/graph: {str(e)}")
        return jsonify({'error': f'Error generando grafo: {str(e)}'}), 500

@app.route('/api/find_shortest_path', methods=['GET'])
def find_shortest_path():
    global current_data
    if current_data is None:
        return jsonify({'error': 'No hay datos cargados para calcular la ruta'}), 400

    source = request.args.get('source')
    target = request.args.get('target')
    stops_str = request.args.get('stops', '')
    stops = [s.strip() for s in stops_str.split(',') if s.strip()]

    if not source or not target:
        return jsonify({'error': 'Debe especificar origen y destino'}), 400

    try:
        G = generate_full_latency_graph()
        full_path = []
        total_latency = 0.0

        # Crear la secuencia de tramos a calcular: (Origen, P1), (P1, P2), ..., (Pn, Destino)
        path_sequence = []
        
        if not stops:
            path_sequence.append((source, target))
        else:
            # Origen a primera parada
            path_sequence.append((source, stops[0]))
            # Paradas intermedias
            for i in range(len(stops) - 1):
                path_sequence.append((stops[i], stops[i+1]))
            # Última parada a Destino
            path_sequence.append((stops[-1], target))

        # Iterar sobre la secuencia de tramos (Dijkstra para cada tramo)
        for i, (src, dst) in enumerate(path_sequence):
            
            if src not in G.nodes or dst not in G.nodes:
                return jsonify({'error': f"Nodo '{src}' o '{dst}' no existe en el grafo"}), 400

            path = nx.shortest_path(G, source=src, target=dst, weight='weight')
            distance = nx.shortest_path_length(G, source=src, target=dst, weight='weight')
            
            total_latency += distance
            
            # Combinar caminos, eliminando duplicados
            if i == 0:
                full_path.extend(path)
            else:
                full_path.extend(path[1:])

        # Generar la lista de aristas del camino
        path_edges = []
        for i in range(len(full_path) - 1):
            u, v = full_path[i], full_path[i+1]
            # Usar G[u][v][0] para manejar aristas paralelas, aunque NetworkX shortest_path elige una
            weight = G[u][v]['weight']
            path_edges.append({'from': u, 'to': v, 'weight': weight})


        return jsonify({
            'path': full_path,
            'latency': round(total_latency, 2),
            'edges': path_edges
        })

    except nx.NetworkXNoPath:
        return jsonify({'error': 'No existe un camino entre los nodos especificados o a través de las paradas.'}), 404
    except Exception as e:
        print(f"Error calculando ruta: {str(e)}")
        return jsonify({'error': f'Error interno calculando ruta: {str(e)}'}), 500

@app.route('/api/data-info', methods=['GET'])
def get_data_info():
    global current_data
    
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'loaded': False})
    
    try:
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
            'columns': current_data.columns.tolist()
        })
    except Exception as e:
        return jsonify({'error': f'Error obteniendo información: {str(e)}'}), 500

@app.route('/api/download', methods=['GET'])
def download_file():
    global current_data
    
    if current_data is None:
        load_last_data()
        if current_data is None:
            return jsonify({'error': 'No hay datos para descargar'}), 400
    
    try:
        download_filename = f"network_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], download_filename)
        
        # Remover la columna ID temporal antes de descargar
        download_data = current_data.drop('id', axis=1, errors='ignore')
        download_data.to_csv(filepath, index=False)
        
        return send_file(filepath, as_attachment=True, download_name=download_filename)
        
    except Exception as e:
        return jsonify({'error': f'Error descargando archivo: {str(e)}'}), 500

if __name__ == '__main__':
    load_last_data() # Intenta cargar al inicio
    app.run(debug=True, host='0.0.0.0', port=5000)