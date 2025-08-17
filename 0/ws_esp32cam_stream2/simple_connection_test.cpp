#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "SAMSUNG";      
const char* password = "panzer790"; 
const char* test_url = "http://smart-cctv-rash32.chbk.app";

void setup() {
  Serial.begin(9600);
  Serial.println("Simple Connection Test Starting...");
  
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
  
  // تست اتصال HTTP
  Serial.println("Testing HTTP connection...");
  
  HTTPClient http;
  http.begin(test_url);
  
  int httpCode = http.GET();
  Serial.print("HTTP Response code: ");
  Serial.println(httpCode);
  
  if (httpCode > 0) {
    String payload = http.getString();
    Serial.println("Response: " + payload.substring(0, 200) + "...");
  } else {
    Serial.println("HTTP request failed");
  }
  
  http.end();
}

void loop() {
  delay(5000);
  Serial.println("System running...");
} 