#include <LiquidCrystal.h>
#include <Servo.h>

// ---------- LCD ----------
const int rs = 12, en = 11, d4 = 5, d5 = 4, d6 = 3, d7 = 2;
LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

// ---------- Servo ----------
Servo myServo;
const int servoPin = 13;

// ---------- Counter ----------
int distracted_counter = 0;
bool busy = false;

// ---------- Display counter ----------
void showCounter() {
  lcd.setCursor(9, 0);
  lcd.print("Cnt:");

  lcd.setCursor(13, 0);
  lcd.print("    ");        // clear old digits
  lcd.setCursor(13, 0);
  lcd.print(distracted_counter);
}

void setup() {
  Serial.begin(9600);
  Serial.println("Arduino RESET");

  lcd.begin(16, 2);
  lcd.print("GET BACK");
  lcd.setCursor(0, 1);
  lcd.print("TO WORK!");

  myServo.attach(servoPin);
  myServo.write(180);

  showCounter();             // show initial 0
}

void loop() {

  if (Serial.available()) {

    // Read full command (handles \n, \r, spam, etc.)
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "F" && !busy) {
      busy = true;

      // ---- Increment counter ----
      distracted_counter++;
      showCounter();

      // ---- Flash LCD 3 times ----
      for (int i = 0; i < 3; i++) {
        lcd.clear();
        delay(300);

        lcd.setCursor(0, 0);
        lcd.print("GET BACK");
        lcd.setCursor(0, 1);
        lcd.print("TO WORK!");
        delay(750);

        showCounter();       // redraw after clear
      }

      // ---- Servo ----
      myServo.write(0);
      delay(1000);
      myServo.write(180);

      showCounter();

      busy = false;
    }
  }
}
