/*
  Arduino Uno R4 WiFi - Sensor HTTP Client
  
  Lee datos de sensores ADC (turbidez, pH, conductividad)
  y los envía a un servidor mediante peticiones HTTP POST.
*/

#include "WiFiS3.h"
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// Definiciones para WiFi de arduino_secrets.h
char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS;

// Definición de pines ADC
#define TURBIDITY_PIN A0
#define PH_PIN        A2
#define CONDUCT_PIN   A4

// Configuración del servidor
const char* server_host = "18.100.55.6";
const int server_port = 8000;
const char* server_path = "/water-monitor/publish";

// Intervalo de actualización (milisegundos)
const unsigned long UPDATE_INTERVAL = 1000;

// Cliente WiFi
WiFiClient client;

// Variables globales
unsigned long lastUpdateTime = 0;
int status = WL_IDLE_STATUS;

// Prototipos de funciones
uint16_t leer_adc(uint8_t pin);
float convertir_turbidez(uint16_t raw);
float convertir_ph(uint16_t raw);
float convertir_salinidad(uint16_t raw);
void conectar_wifi();
void enviar_datos_sensores();

void setup() {
  // Inicializar serial
  Serial.begin(9600);
  while (!Serial) {
    ; // Esperar a que el puerto serial se conecte
  }
  
  // Configurar ADC para resolución de 12 bits
  analogReadResolution(12);
  
  // Conectar a WiFi
  conectar_wifi();
}

void loop() {
  // Verificar conexión WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Reconectando a WiFi...");
    conectar_wifi();
    return;
  }
  
  // Verificar si es tiempo de enviar una actualización
  unsigned long currentTime = millis();
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    lastUpdateTime = currentTime;
    enviar_datos_sensores();
  }
}

void conectar_wifi() {
  // Verificar el módulo WiFi
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("¡Fallo en comunicación con módulo WiFi!");
    while (true); // No continuar
  }
  
  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Por favor actualice el firmware");
  }
  
  // Intentar conectar a la red WiFi
  while (status != WL_CONNECTED) {
    Serial.print("Intentando conectar a SSID: ");
    Serial.println(ssid);
    
    // Conectar a red WPA/WPA2
    status = WiFi.begin(ssid, pass);
    
    // Esperar 10 segundos para la conexión
    delay(5000);
  }
  
  Serial.println("Conectado a WiFi");
  
  // Imprimir estado de WiFi
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());
  
  // Imprimir dirección IP
  IPAddress ip = WiFi.localIP();
  Serial.print("Dirección IP: ");
  Serial.println(ip);
}

void enviar_datos_sensores() {
  // Leer valores de los sensores
  uint16_t turbidez_raw = leer_adc(TURBIDITY_PIN);
  uint16_t ph_raw = leer_adc(PH_PIN);
  uint16_t conductividad_raw = leer_adc(CONDUCT_PIN);
  
  // Convertir a valores estandarizados
  float turbidez = convertir_turbidez(turbidez_raw);
  float ph = convertir_ph(ph_raw);
  float salinidad = convertir_salinidad(conductividad_raw);
  
  // Imprimir formato Arduino para referencia
  Serial.print("Formato Arduino: T:");
  Serial.print(turbidez, 2);
  Serial.print(";PH:");
  Serial.print(ph, 2);
  Serial.print(";C:");
  Serial.print(salinidad, 2);
  Serial.println();
  
  float turbidez_redondeado = round(turbidez * 100) / 100.0;
  float ph_redondeado = round(ph * 100) / 100.0;
  float salinidad_redondeado = round(salinidad * 100) / 100.0;
  
  StaticJsonDocument<200> doc;
  doc["T"] = turbidez_redondeado;
  doc["PH"] = ph_redondeado;
  doc["C"] = salinidad_redondeado;
  
  // Serializar JSON a String
  String json;
  serializeJson(doc, json);
  
  Serial.print("Enviando datos: ");
  Serial.println(json);
  
  // Conectar al servidor
  Serial.print("Conectando a ");
  Serial.println(server_host);
  
  if (client.connect(server_host, server_port)) {
    Serial.println("Conectado al servidor...");
    
    // Preparar solicitud HTTP POST
    client.println("POST " + String(server_path) + " HTTP/1.1");
    client.println("Host: " + String(server_host));
    client.println("Connection: close");
    client.println("Content-Type: application/json");
    client.println("Accept: application/json");  // Añadir encabezado Accept
    client.println("User-Agent: ArduinoR4Client/1.0");  // Añadir User-Agent
    client.print("Content-Length: ");
    client.println(json.length());
    client.println();  // Línea en blanco entre encabezados y cuerpo
    client.print(json);  // Usar print en lugar de println para el cuerpo
    
    // Esperar respuesta del servidor
    unsigned long timeout = millis();
    while (client.connected() && millis() - timeout < 10000) {
      if (client.available()) {
        String line = client.readStringUntil('\n');
        Serial.println(line);
        if (line == "\r") {
          break;
        }
      }
    }
    
    // Leer el cuerpo de la respuesta
    while (client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println(line);
    }
    
    client.stop();
    Serial.println("Conexión cerrada");
  } else {
    Serial.println("Fallo en conexión al servidor");
    client.stop();
  }
}

// Función para leer ADC con promedio
uint16_t leer_adc(uint8_t pin) {
  uint32_t sum = 0;
  const int samples = 10;
  
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  
  return sum / samples;
}

// Función para convertir valor raw de turbidez (invertido)
float convertir_turbidez(uint16_t raw) {
  return 1000.0 * (1.0 - (float)raw / 4095.0);
}

// Función para convertir valor raw de pH
float convertir_ph(uint16_t raw) {
  return 14.0 * ((float)raw / 4095.0);
}

// Función para convertir valor raw de salinidad
float convertir_salinidad(uint16_t raw) {
  return 1500.0 * ((float)raw / 4095.0);
}