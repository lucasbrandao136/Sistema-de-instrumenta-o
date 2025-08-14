
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "GABRIEL"; // sua rede
const char* password = "W3#FUu7WRgg!"; // sua senha

#define PIN_SENSOR 0 // GPIO0 - sensor
#define PIN_VERDE 2 // GPIO2 - LED verde
#define PIN_AMARELO 1 // GPIO1 (TX) - LED amarelo
#define PIN_BRANCO 3 // GPIO3 (RX) - LED branco

//  UDP
WiFiUDP udp;
const unsigned int localPort = 8889; // Porta do ESP
const unsigned int pcPort = 8888; // Porta do PC
IPAddress broadcastAddress(255, 255, 255, 255); 

// Variáveis de estado e dados
enum State { WAITING_HANDSHAKE, MONITORING_SENSORS };
State currentState = WAITING_HANDSHAKE;

String espId = "";
IPAddress pcIp;

unsigned long lastHandshakeRequest = 0;
const long handshakeInterval = 1000; 

bool obstacleDetected = false;

// Variáveis para o LED branco
unsigned long blinkStartTime = 0;
bool isBlinking = false;
int blinkCount = 0;
const int totalBlinks = 10; 

void setup() {
  pinMode(PIN_SENSOR, INPUT_PULLUP);
  pinMode(PIN_VERDE, OUTPUT);
  pinMode(PIN_AMARELO, OUTPUT);
  pinMode(PIN_BRANCO, OUTPUT);

  digitalWrite(PIN_VERDE, LOW);
  digitalWrite(PIN_BRANCO, LOW);
  digitalWrite(PIN_AMARELO, HIGH); 

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  udp.begin(localPort);
}

void loop() {
  switch (currentState) {
    case WAITING_HANDSHAKE:
      handleHandshake();
      break;
    case MONITORING_SENSORS:
      handleSensorMonitoring();
      break;
  }
  
  handleWhiteLedBlinking();

  checkUdpCommands();
}

void handleHandshake() {
  unsigned long currentMillis = millis();
  if (currentMillis - lastHandshakeRequest >= handshakeInterval) {
    lastHandshakeRequest = currentMillis;
    

    udp.beginPacket(broadcastAddress, pcPort);
    udp.write("handshake_request");
    udp.endPacket();
  }
}

void handleSensorMonitoring() {
  int sensorValue = digitalRead(PIN_SENSOR);

  if (sensorValue == HIGH && !obstacleDetected) {
    digitalWrite(PIN_VERDE, HIGH);
    obstacleDetected = true;

    String message = "object_detected:" + espId;
    udp.beginPacket(pcIp, pcPort);
    udp.write(message.c_str());
    udp.endPacket();

  } else if (sensorValue == LOW && obstacleDetected) {
    digitalWrite(PIN_VERDE, LOW);
  }
}

void handleWhiteLedBlinking() {
  if (isBlinking) {
    unsigned long currentMillis = millis();
    if (currentMillis - blinkStartTime >= 500) {
      blinkStartTime = currentMillis;
      digitalWrite(PIN_BRANCO, !digitalRead(PIN_BRANCO)); 
      blinkCount++;
      if (blinkCount >= totalBlinks) {
        isBlinking = false;
        blinkCount = 0;
        digitalWrite(PIN_BRANCO, LOW); 
      }
    }
  }
}

void checkUdpCommands() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    char buffer[255];
    udp.read(buffer, packetSize);
    buffer[packetSize] = '\0';
    String msg = String(buffer);

    if (currentState == WAITING_HANDSHAKE && msg.startsWith("id:")) {
      espId = msg.substring(3);
      pcIp = udp.remoteIP();
      
      currentState = MONITORING_SENSORS;
      digitalWrite(PIN_AMARELO, LOW); 
      return;
    }

    if (currentState == MONITORING_SENSORS) {
      if (msg == "blink_white_led") {
          isBlinking = true;
          blinkStartTime = millis();
          blinkCount = 0;
      }
      
      if (msg == "forget_obstacle") {
        obstacleDetected = false;
        digitalWrite(PIN_VERDE, LOW);
      }
      
      if (msg == "cancel_handshake") {
        currentState = WAITING_HANDSHAKE;
        digitalWrite(PIN_AMARELO, HIGH);
        espId = "";
        obstacleDetected = false;
        digitalWrite(PIN_VERDE, LOW);
      }
    }
  }
}
