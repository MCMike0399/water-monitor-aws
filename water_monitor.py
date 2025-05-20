from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import json
import logging
import asyncio
from datetime import datetime
import os
import random
from fastapi_websocket_pubsub import PubSubEndpoint

logger = logging.getLogger(__name__)

# Inicializar endpoint PubSub
pubsub_endpoint = PubSubEndpoint()

# Almacenar datos más recientes
latest_data = {
    "T": 25.0,  # Turbidez
    "PH": 7.0,  # pH
    "C": 300.0  # Conductividad
}

# Variable para controlar el modo (mock o real)
use_mock_data = True
mock_data_task = None

async def http_publisher_endpoint(request: Request):
    """Endpoint HTTP para publicadores (Arduino)"""
    global latest_data, use_mock_data
    
    try:
        # Parsear el cuerpo de la petición como JSON
        json_data = await request.json()
        logger.info(f"Datos HTTP recibidos: {json_data}")
        
        # Si no estamos en modo mock, actualizar datos
        if not use_mock_data and all(key in json_data for key in ["T", "PH", "C"]):
            latest_data = {
                "T": float(json_data["T"]),
                "PH": float(json_data["PH"]),
                "C": float(json_data["C"])
            }
            logger.info(f"Datos actualizados (HTTP): {latest_data}")
            return JSONResponse(content={"status": "ok", "message": "Datos recibidos"})
        else:
            return JSONResponse(content={
                "status": "info",
                "message": f"Datos {'ignorados (modo mock activo)' if use_mock_data else 'incompletos'}"
            })
            
    except json.JSONDecodeError:
        logger.warning("JSON inválido recibido (HTTP)")
        return JSONResponse(content={"status": "error", "message": "Formato JSON inválido"}, status_code=400)
    except Exception as e:
        logger.error(f"Error en endpoint HTTP: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Endpoint para publicadores (Arduino)
async def publisher_endpoint(websocket: WebSocket):
    """Endpoint WebSocket para publicadores (Arduino)"""
    global latest_data, use_mock_data
    
    await websocket.accept()
    logger.info("Nueva conexión de publicador establecida")
    
    try:
        # Manejar mensajes del publicador
        while True:
            data = await websocket.receive_text()
            try:
                # Parsear mensaje JSON
                json_data = json.loads(data)
                logger.info(f"Datos recibidos de publicador: {json_data}")
                
                # Comprobar si es un comando de control
                if "command" in json_data:
                    if json_data["command"] == "use_mock_data":
                        use_mock_data = json_data.get("value", True)
                        logger.info(f"Modo de datos cambiado: use_mock_data = {use_mock_data}")
                        await websocket.send_json({"status": "ok", "message": f"Modo cambiado a {'mock' if use_mock_data else 'real'}"})
                        continue
                
                # Si no estamos en modo mock, actualizar datos
                if not use_mock_data and all(key in json_data for key in ["T", "PH", "C"]):
                    latest_data = {
                        "T": float(json_data["T"]),
                        "PH": float(json_data["PH"]),
                        "C": float(json_data["C"])
                    }
                    logger.info(f"Datos actualizados: {latest_data}")
                    await websocket.send_json({"status": "ok", "message": "Datos recibidos"})
                else:
                    await websocket.send_json({
                        "status": "info",
                        "message": f"Datos {'ignorados (modo mock activo)' if use_mock_data else 'incompletos'}"
                    })
                
            except json.JSONDecodeError:
                logger.warning(f"JSON inválido recibido: {data}")
                await websocket.send_text(f"Formato JSON inválido: {data}")
                
    except WebSocketDisconnect:
        logger.info("Publicador desconectado")
    except Exception as e:
        logger.error(f"Error en WebSocket de publicador: {str(e)}")

async def client_endpoint(websocket: WebSocket):
    """Endpoint WebSocket tradicional para clientes web"""
    await websocket.accept()
    logger.info("Nueva conexión de cliente establecida")
    
    # Tarea para enviar actualizaciones periódicas al cliente
    async def send_periodic_updates():
        while True:
            try:
                await websocket.send_json(latest_data)
                await asyncio.sleep(3.0)  # Usar el mismo intervalo que generate_mock_data
            except Exception:
                # Si hay un error, terminar la tarea
                break
    
    # Iniciar tarea de actualizaciones periódicas
    update_task = asyncio.create_task(send_periodic_updates())
    
    try:
        # Enviar datos iniciales inmediatamente
        await websocket.send_json(latest_data)
        
        # Mantener conexión abierta para procesar mensajes del cliente
        while True:
            # Esperar mensaje del cliente
            data = await websocket.receive_text()
            try:
                json_data = json.loads(data)
                logger.info(f"Mensaje recibido del cliente: {json_data}")
                
                # Responder con eco
                await websocket.send_json({
                    "status": "echo", 
                    "data": json_data,
                    "timestamp": datetime.now().isoformat()
                })
                
            except json.JSONDecodeError:
                logger.warning(f"JSON inválido del cliente: {data}")
                
    except WebSocketDisconnect:
        logger.info("Cliente desconectado")
    except Exception as e:
        logger.error(f"Error en WebSocket de cliente: {str(e)}")
    finally:
        # Asegurar que la tarea de actualizaciones se cancele cuando el cliente se desconecta
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass

# Generar datos de prueba
async def generate_mock_data(interval: float = 3.0):
    """Generar datos de sensores aleatorios para pruebas"""
    global latest_data
    logger.info(f"Iniciando generación de datos mock cada {interval}s")
    
    while True:
        # Solo generar datos si el modo mock está activo
        if use_mock_data:
            # Generar valores aleatorios en rangos realistas
            mock_data = {
                "T": round(random.uniform(5, 800), 2),    # Turbidez (NTU)
                "PH": round(random.uniform(3, 10), 2),    # pH
                "C": round(random.uniform(100, 1200), 2)  # Conductividad (μS/cm)
            }
            
            # Actualizar datos más recientes
            latest_data = mock_data
            logger.debug(f"Datos mock generados: {mock_data}")
        
        # Publicar datos a todos los suscriptores
        await pubsub_endpoint.publish("water_data", latest_data)
        logger.debug(f"Datos publicados: {latest_data}")
        
        # Esperar intervalo
        await asyncio.sleep(interval)

# Interfaz web para control
async def get_control_page():
    """Devuelve la página HTML de control"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control de Monitor de Agua</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .panel { background: #f0f0f0; padding: 15px; border-radius: 5px; }
            button { padding: 10px 15px; margin: 5px; }
            .active { background: #4CAF50; color: white; }
            .inactive { background: #f44336; color: white; }
        </style>
    </head>
    <body>
        <h1>Panel de Control</h1>
        <div class="panel">
            <h2>Modo de Datos</h2>
            <button id="mockBtn" onclick="setMode(true)">Datos Simulados</button>
            <button id="realBtn" onclick="setMode(false)">Datos Reales (Arduino)</button>
            <p id="status">Estado: Conectando...</p>
        </div>

        <script>
            let socket;
            
            function connectWebSocket() {
                socket = new WebSocket('ws://' + window.location.host + '/water-monitor/publish');
                
                socket.onopen = function() {
                    document.getElementById('status').textContent = 'Estado: Conectado';
                    // Consultar estado actual
                    socket.send(JSON.stringify({command: 'get_mode'}));
                };
                
                socket.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    document.getElementById('status').textContent = 'Estado: ' + data.message;
                    
                    // Actualizar botones si se recibe información de modo
                    if(data.mode !== undefined) {
                        updateButtons(data.mode);
                    }
                };
                
                socket.onclose = function() {
                    document.getElementById('status').textContent = 'Estado: Desconectado';
                    setTimeout(connectWebSocket, 2000);
                };
            }
            
            function setMode(useMock) {
                if(socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        command: 'use_mock_data',
                        value: useMock
                    }));
                    updateButtons(useMock);
                }
            }
            
            function updateButtons(useMock) {
                const mockBtn = document.getElementById('mockBtn');
                const realBtn = document.getElementById('realBtn');
                
                if(useMock) {
                    mockBtn.className = 'active';
                    realBtn.className = 'inactive';
                } else {
                    mockBtn.className = 'inactive';
                    realBtn.className = 'active';
                }
            }
            
            // Conectar al cargar la página
            window.onload = connectWebSocket;
        </script>
    </body>
    </html>
    """)

def setup_static_files(app: FastAPI):
    """Configurar archivos estáticos"""
    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info(f"Directorio de archivos estáticos montado: {static_dir}")
    else:
        os.makedirs(static_dir, exist_ok=True)
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info(f"Directorio de archivos estáticos creado: {static_dir}")

def register_routes(app: FastAPI):
    """Registrar rutas de la aplicación"""
    # Montar endpoint PubSub
    pubsub_endpoint.register_route(app.router, path="/water-pubsub")
    
    # Configurar archivos estáticos
    setup_static_files(app)
    
    # Página de monitoreo actual
    @app.get("/water-monitor")
    async def get_water_monitor():
        html_path = os.path.join(os.getcwd(), "static", "ws_client.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        else:
            return HTMLResponse("<html><body><h1>Página de monitoreo no encontrada</h1></body></html>")
    
    # Página de control
    app.get("/water-monitor/control")(get_control_page)
    
    # Endpoint HTTP POST para Arduino
    app.post("/water-monitor/publish")(http_publisher_endpoint)
    
    # Endpoints WebSocket
    app.websocket("/water-monitor/publish")(publisher_endpoint)
    app.websocket("/water-monitor")(client_endpoint)
    
    # Iniciar tarea de datos mock en startup
    @app.on_event("startup")
    async def startup_event():
        global mock_data_task
        mock_data_task = asyncio.create_task(generate_mock_data(interval=3.0))
        logger.info("Tarea de generación de datos mock iniciada")
    
    # Cancelar tarea en shutdown
    @app.on_event("shutdown")
    async def shutdown_event():
        global mock_data_task
        if mock_data_task:
            mock_data_task.cancel()
            try:
                await mock_data_task
            except asyncio.CancelledError:
                logger.info("Tarea de datos mock cancelada")
    
    logger.info("Rutas de monitoreo registradas")