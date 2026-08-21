/*
 * PAN (D9) 범위 테스트 — 어디부터 어디까지 안전하게 도는지 확인
 *
 * 속도: 20ms/° (180° = 3.6초, 객체 추적 기준 속도 동일)
 *
 * Serial 명령 (한 글자, Enter 필요할 수도):
 *   1  →  +10° 회전 (오른쪽)
 *   2  →  FREEZE — 현재 위치 정지 (PWM 끔)
 *   3  →  Recenter to 90° (재 calibration)
 *   4  →  -10° 회전 (왼쪽)
 *   s  →  현재 각도 출력
 *   ?  →  도움말
 *
 * 사용 흐름 (PAN 범위 탐색):
 *   3 → 90°로 calibration
 *   1 누름 × N회 → 오른쪽 끝까지 (limit 확인)
 *   3 → 다시 90°
 *   4 누름 × N회 → 왼쪽 끝까지 (limit 확인)
 *   2 → 만족스러운 위치에서 freeze
 *
 * 각 명령 후 [STATUS] PAN = N° 자동 출력.
 */

#include <Servo.h>

#define SERVO_PIN     9      // D9 = PAN 핀
#define STEP_DELAY    20     // ms/° — 회전 속도 (객체 추적 기준)
#define STEP_SIZE     10     // 1/4 명령 1회당 각도
#define ANGLE_MIN     0
#define ANGLE_MAX     180
#define ANGLE_CENTER  90

Servo pan_servo;
int current_angle = ANGLE_CENTER;
bool attached = true;

void slow_move_to(int target);
void recenter();
void freeze_servo();
void unfreeze_servo();
void print_status();
void print_help();

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000);

    Serial.println();
    Serial.println("======================================");
    Serial.println(" PAN (D9) Range Test ");
    Serial.println("======================================");
    Serial.print("Pin: D"); Serial.println(SERVO_PIN);
    Serial.print("Speed: "); Serial.print(STEP_DELAY); Serial.println(" ms/deg");
    Serial.print("Step:  "); Serial.print(STEP_SIZE); Serial.println(" deg per press");
    print_help();

    pan_servo.attach(SERVO_PIN);
    pan_servo.write(current_angle);
    delay(500);
    print_status();
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();

        // 공백 / 줄바꿈 무시
        if (c == '\n' || c == '\r' || c == ' ') return;

        if (c == '1') {
            if (!attached) unfreeze_servo();
            int target = constrain(current_angle + STEP_SIZE, ANGLE_MIN, ANGLE_MAX);
            Serial.print("[1] +"); Serial.print(STEP_SIZE);
            Serial.print(" deg : "); Serial.print(current_angle);
            Serial.print(" -> "); Serial.print(target);
            if (target == current_angle + STEP_SIZE) Serial.println("");
            else { Serial.print(" (capped at "); Serial.print(ANGLE_MAX); Serial.println(")"); }
            slow_move_to(target);
            print_status();
        }
        else if (c == '2') {
            freeze_servo();
        }
        else if (c == '3') {
            if (!attached) unfreeze_servo();
            Serial.println("[3] Recenter to 90 deg ...");
            slow_move_to(ANGLE_CENTER);
            print_status();
        }
        else if (c == '4') {
            if (!attached) unfreeze_servo();
            int target = constrain(current_angle - STEP_SIZE, ANGLE_MIN, ANGLE_MAX);
            Serial.print("[4] -"); Serial.print(STEP_SIZE);
            Serial.print(" deg : "); Serial.print(current_angle);
            Serial.print(" -> "); Serial.print(target);
            if (target == current_angle - STEP_SIZE) Serial.println("");
            else { Serial.print(" (capped at "); Serial.print(ANGLE_MIN); Serial.println(")"); }
            slow_move_to(target);
            print_status();
        }
        else if (c == 's' || c == 'S') {
            print_status();
        }
        else if (c == '?' || c == 'h' || c == 'H') {
            print_help();
        }
        else {
            Serial.print("Unknown: '"); Serial.print(c); Serial.println("'  (use 1/2/3/4)");
        }
    }
}

/* 1°씩 천천히 이동 — 객체 추적 기준 속도 (20ms/°) */
void slow_move_to(int target) {
    if (target == current_angle) {
        Serial.println("   (already at target)");
        return;
    }
    int dir = (target > current_angle) ? 1 : -1;
    while (current_angle != target) {
        current_angle += dir;
        pan_servo.write(current_angle);
        delay(STEP_DELAY);
    }
}

void freeze_servo() {
    if (attached) {
        pan_servo.detach();
        attached = false;
        Serial.print("[2] FROZEN at "); Serial.print(current_angle);
        Serial.println(" deg  (PWM off, no holding)");
    } else {
        Serial.print("[2] Already frozen at "); Serial.print(current_angle);
        Serial.println(" deg");
    }
}

void unfreeze_servo() {
    pan_servo.attach(SERVO_PIN);
    pan_servo.write(current_angle);
    attached = true;
    Serial.println("   (re-attached)");
}

void print_status() {
    Serial.print("[STATUS] PAN = "); Serial.print(current_angle); Serial.print(" deg  ");
    Serial.println(attached ? "(attached)" : "(FROZEN)");
}

void print_help() {
    Serial.println();
    Serial.println("--- Commands ---");
    Serial.println("  1   +10 deg  (right)");
    Serial.println("  2   FREEZE   (stop and hold position)");
    Serial.println("  3   Recenter to 90 deg");
    Serial.println("  4   -10 deg  (left)");
    Serial.println("  s   show current angle");
    Serial.println("  ?   help");
    Serial.println();
}
