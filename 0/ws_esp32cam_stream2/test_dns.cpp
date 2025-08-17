#include <WiFi.h>

const char* ssid = "SAMSUNG";      
const char* password = "panzer790"; 
const char* test_host = "smart-cctv-rash32.chbk.app";

void setup() {
  Serial.begin(9600);
  Serial.println("DNS Test Starting...");
  
  // اتصال به WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  // تست DNS resolution
  Serial.println("Testing DNS resolution...");
  
  IPAddress serverIP;
  Serial.println("Attempting to resolve: " + String(test_host));
  
  if (WiFi.hostByName(test_host, serverIP, 10000)) {
    Serial.println("DNS resolution SUCCESSFUL!");
    Serial.println("Resolved IP: " + serverIP.toString());
  } else {
    Serial.println("DNS resolution FAILED!");
    
    // تست DNS سرورهای جایگزین
    Serial.println("Trying alternative DNS servers...");
    
    IPAddress primaryDNS(8, 8, 8, 8);    // Google DNS
    IPAddress secondaryDNS(1, 1, 1, 1);  // Cloudflare DNS
    WiFi.setDNS(primaryDNS, secondaryDNS);
    
    delay(2000);
    
    if (WiFi.hostByName(test_host, serverIP, 10000)) {
      Serial.println("DNS resolution SUCCESSFUL with alternative DNS!");
      Serial.println("Resolved IP: " + serverIP.toString());
    } else {
      Serial.println("DNS resolution FAILED even with alternative DNS!");
    }
  }
  
  // تست اتصال HTTP
  Serial.println("Testing HTTP connection...");
  WiFiClient client;
  if (client.connect(test_host, 80)) {
    Serial.println("HTTP connection SUCCESSFUL!");
    client.println("GET / HTTP/1.1");
    client.println("Host: " + String(test_host));
    client.println("Connection: close");
    client.println();
    
    delay(1000);
    
    while (client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println(line);
    }
    
    client.stop();
  } else {
    Serial.println("HTTP connection FAILED!");
  }
}

void loop() {
  delay(10000);
  Serial.println("System still running...");
} 