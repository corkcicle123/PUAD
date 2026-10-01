/**
 * Arduino Smart QA Conveyor Belt Controller
 * Capstone Project: Electronic Component Anomaly Detection System
 * 
 * Hardware Setup:
 * - Pin 2:  IR Proximity Sensor (Object detection)
 * - Pin 9:  Conveyor Motor PWM (Speed control)
 * - Pin 8:  Conveyor Motor Direction (DIR)
 * - Pin 10: Reject Servo Motor (Part sorter)
 * - Pin 11: Green LED (PASS Indicator)
 * - Pin 12: Red LED (FAIL Indicator)
 * - Pin 13: Buzzer (Defect alarm)
 */

#include <Servo.h>

// Pin Definitions
const int PIN_IR_SENSOR  = 2;
const int PIN_MOTOR_PWM  = 9;
const int PIN_MOTOR_DIR  = 8;
const int PIN_SERVO      = 10;
const int PIN_LED_PASS   = 11;
const int PIN_LED_FAIL   = 12;
const int PIN_BUZZER     = 13;

// Servo Angles
const int SERVO_PASS_ANGLE   = 0;   // Normal straight path
const int SERVO_REJECT_ANGLE = 60;  // Divert into defect bin

// State variables
Servo sorterServo;
bool conveyorRunning = true;
unsigned long lastTriggerTime = 0;
const unsigned long TRIGGER_DEBOUNCE_MS = 1500; // Prevent multi-triggers on same part

void setup() {
  Serial.begin(115200);
  
  pinMode(PIN_IR_SENSOR, INPUT_PULLUP);
  pinMode(PIN_MOTOR_PWM, OUTPUT);
  pinMode(PIN_MOTOR_DIR, OUTPUT);
  pinMode(PIN_LED_PASS, OUTPUT);
  pinMode(PIN_LED_FAIL, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  
  sorterServo.attach(PIN_SERVO);
  sorterServo.write(SERVO_PASS_ANGLE);
  
  // Power-on self test: flash LEDs
  digitalWrite(PIN_LED_PASS, HIGH);
  digitalWrite(PIN_LED_FAIL, HIGH);
  delay(300);
  digitalWrite(PIN_LED_PASS, LOW);
  digitalWrite(PIN_LED_FAIL, LOW);
  
  // Start conveyor belt forward
  startConveyor(180); // Speed 0-255
  
  Serial.println("ARDUINO_READY");
}

void loop() {
  // 1. Read IR Sensor to detect incoming component
  int sensorVal = digitalRead(PIN_IR_SENSOR);
  unsigned long now = millis();
  
  // Object detected (Active LOW for most IR sensors)
  if (sensorVal == LOW && (now - lastTriggerTime > TRIGGER_DEBOUNCE_MS)) {
    lastTriggerTime = now;
    
    // Stop conveyor under webcam inspection area
    stopConveyor();
    delay(200); // Wait for vibration to settle
    
    // Send trigger to Python inspection software
    Serial.println("TRIGGER");
  }
  
  // 2. Read Serial commands from Python
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "PASS") {
      handlePassVerdict();
    } else if (command == "FAIL") {
      handleFailVerdict();
    } else if (command == "START") {
      startConveyor(180);
    } else if (command == "STOP") {
      stopConveyor();
    } else if (command == "TEST_SERVO") {
      sorterServo.write(SERVO_REJECT_ANGLE);
      delay(500);
      sorterServo.write(SERVO_PASS_ANGLE);
    }
  }
}

void startConveyor(int speed) {
  digitalWrite(PIN_MOTOR_DIR, HIGH);
  analogWrite(PIN_MOTOR_PWM, speed);
  conveyorRunning = true;
}

void stopConveyor() {
  analogWrite(PIN_MOTOR_PWM, 0);
  conveyorRunning = false;
}

void handlePassVerdict() {
  // Indicate PASS
  digitalWrite(PIN_LED_PASS, HIGH);
  delay(200);
  digitalWrite(PIN_LED_PASS, LOW);
  
  // Keep servo in pass lane and advance conveyor
  sorterServo.write(SERVO_PASS_ANGLE);
  startConveyor(180);
}

void handleFailVerdict() {
  // Alarm
  digitalWrite(PIN_LED_FAIL, HIGH);
  tone(PIN_BUZZER, 1000, 250);
  
  // Actuate Reject Diverter Arm
  sorterServo.write(SERVO_REJECT_ANGLE);
  delay(150);
  
  // Run conveyor forward briefly to push part into defect bin
  startConveyor(200);
  delay(700);
  
  // Reset servo to straight path
  sorterServo.write(SERVO_PASS_ANGLE);
  digitalWrite(PIN_LED_FAIL, LOW);
}
