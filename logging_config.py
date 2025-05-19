import logging
import os
import colorlog
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


def setup_logging(log_level=logging.DEBUG):
    """
    Configura el sistema de logging para toda la aplicación.
    
    Args:
        log_level: Nivel de logging (por defecto INFO)
        
    Returns:
        logger: El logger raíz configurado
    """
    # Crear directorio para logs si no existe
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Crear nombre de archivo con fecha
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"monitor-de-agua-en-tiempo-real_{today}.log")
    
    # Obtener logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Eliminar handlers existentes para evitar duplicados
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Formato detallado para los logs
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Formato con colores para la consola
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s" + log_format,
        datefmt=date_format,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Formato para archivo
    file_formatter = logging.Formatter(log_format, date_format)
    
    # Handler para consola con colores
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Handler para archivo con rotación por tamaño (10MB)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    # Handler para archivo con rotación diaria
    daily_handler = TimedRotatingFileHandler(
        log_file.replace('.log', '_daily.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    daily_handler.setFormatter(file_formatter)
    daily_handler.setLevel(log_level)
    root_logger.addHandler(daily_handler)
    
    # Configuración específica para módulos
    #logging.getLogger("selenium").setLevel(logging.WARNING)
    #logging.getLogger("urllib3").setLevel(logging.WARNING)
    #logging.getLogger("CaptchaSolver").setLevel(logging.DEBUG)
    #logging.getLogger("solveCaptcha").setLevel(logging.DEBUG)
    
    # Log de inicio
    root_logger.info("="*70)
    root_logger.info(f"INICIO DE SESIÓN NEXUS BOT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    root_logger.info(f"Log file: {log_file}")
    root_logger.info("="*70)
    
    return root_logger

def get_logger(name):
    """
    Obtiene un logger con el nombre especificado.
    
    Args:
        name: Nombre del logger (generalmente __name__)
        
    Returns:
        Un logger configurado
    """
    return logging.getLogger(name)