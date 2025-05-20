/*
  Arduino Uno R4 WiFi - Sensor HTTP Client
  
  Reads ADC sensor data (turbidity, pH, conductivity)
  and sends it to a server via HTTP POST requests.
*/

#include "WiFiS3.h"
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// WiFi credentials from arduino_secrets.h
char ssid[] = SECRET_SSID;
char pass[] = SECRET_PASS;

// ADC Pin definitions
#define TURBIDITY_PIN A0
#define PH_PIN        A1
#define CONDUCT_PIN   A2

#define USE_KEEP_ALIVE true
const unsigned long RECONNECT_INTERVAL = 60000; // 1 minute
unsigned long lastConnectionTime = 0;
bool isConnected = false;

// Server configuration
const char* server_host = "51.92.64.38";
const int server_port = 8000;
const char* server_path = "/water-monitor/publish";

// Update interval (milliseconds)
const unsigned long UPDATE_INTERVAL = 1000;

// WiFi client
WiFiClient client;

// Global variables
unsigned long lastUpdateTime = 0;
int status = WL_IDLE_STATUS;

// Function prototypes
uint16_t read_adc(uint8_t pin);
float convert_turbidity(uint16_t raw);
float convert_ph(uint16_t raw);
float convert_conductivity(uint16_t raw);
void connect_wifi();
void send_sensor_data();

void setup() {
  // Initialize serial
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  
  // Configure ADC for 12-bit resolution
  analogReadResolution(12);
  
  // Connect to WiFi
  connect_wifi();
}

void loop() {
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Reconnecting to WiFi...");
    connect_wifi();
    return;
  }

  // Check server connection periodically
  if (USE_KEEP_ALIVE && isConnected) {
    unsigned long currentTime = millis();
    if (currentTime - lastConnectionTime >= RECONNECT_INTERVAL) {
      client.stop();
      isConnected = false;
      lastConnectionTime = currentTime;
    }
  }
  
  // Check if it's time to send an update
  unsigned long currentTime = millis();
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    lastUpdateTime = currentTime;
    send_sensor_data();
  }
}

void connect_wifi() {
  // Check WiFi module
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    while (true); // Do not continue
  }
  
  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Please update the firmware");
  }
  
  // Try to connect to WiFi network
  while (status != WL_CONNECTED) {
    Serial.print("Attempting to connect to SSID: ...");
    Serial.println(ssid);
    
    // For open networks (no password)
    if (strlen(pass) == 0) {
      status = WiFi.begin(ssid);
    } else {
      // Connect to WPA/WPA2 network
      status = WiFi.begin(ssid, pass);
    }
    
    // Wait for connection
    delay(5000);
  }
  
  Serial.println("Connected to WiFi");
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);
}

void send_sensor_data() {
  // Read sensors
  uint16_t turbidity_raw = read_adc(TURBIDITY_PIN);
  uint16_t ph_raw = read_adc(PH_PIN);
  uint16_t conductivity_raw = read_adc(CONDUCT_PIN);
  
  // Convert values
  float turbidity = convert_turbidity(turbidity_raw);
  float ph = convert_ph(ph_raw);
  float conductivity = convert_conductivity(conductivity_raw);
  
  // Reduce serial output frequency
  static int print_counter = 0;
  if (++print_counter >= 5) {
    print_counter = 0;
    Serial.print("Data: T:");
    Serial.print(turbidity, 2);
    Serial.print(";PH:");
    Serial.print(ph, 2);
    Serial.print(";C:");
    Serial.println(conductivity, 2);
  }
  
  // Create JSON
  StaticJsonDocument<200> doc;
  doc["T"] = round(turbidity * 100) / 100.0;
  doc["PH"] = round(ph * 100) / 100.0;
  doc["C"] = round(conductivity * 100) / 100.0;
  
  String json;
  serializeJson(doc, json);
  
  // Manage connection
  if (!isConnected) {
    if (!client.connect(server_host, server_port)) {
      Serial.println("Failed to connect to server");
      return;
    }
    isConnected = true;
    Serial.println("Connected to server");
  }
  
  // Minimized HTTP request
  client.print("POST ");
  client.print(server_path);
  client.println(" HTTP/1.1");
  client.print("Host: ");
  client.println(server_host);
  client.println(USE_KEEP_ALIVE ? "Connection: keep-alive" : "Connection: close");
  client.println("Content-Type: application/json");
  client.print("Content-Length: ");
  client.println(json.length());
  client.println();  // Blank line is crucial
  client.print(json);
  client.flush();  // Force data transmission
  
  // Minimal response processing
  unsigned long timeout = millis();
  bool headerEnded = false;
  
  while (client.connected() && (millis() - timeout < 1000)) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      if (line == "\r") {
        headerEnded = true;
        break;
      }
    }
  }
  
  // Drain any remaining response data
  while (client.available()) {
    client.read();
  }

  // Handle connection based on keep-alive setting
  if (!USE_KEEP_ALIVE) {
    client.stop();
    isConnected = false;
  }
}

// Function to read ADC with averaging
uint16_t read_adc(uint8_t pin) {
  uint32_t sum = 0;
  const int samples = 10;
  
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  
  return sum / samples;
}

// Function to convert raw turbidity value (inverted)
float convert_turbidity(uint16_t raw) {
  return 1000.0 * (1.0 - (float)raw / 4095.0);
}

// Function to convert raw pH value
float convert_ph(uint16_t raw) {
  return 14.0 * ((float)raw / 4095.0);
}

// Function to convert raw conductivity value
float convert_conductivity(uint16_t raw) {
  return 1500.0 * ((float)raw / 4095.0);
}