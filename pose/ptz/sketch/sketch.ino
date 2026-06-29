/*
 * PTZ PoC — STM32U585 측 (MCU)
 *
 * 검증 목적: pose 추적용 더 좋은 카메라 각도를 자동 탐색 가능한가?
 * 가설 H1~H4: docs/08_ptz_camera_angle_validation.md
 *
 * 흐름:
 *   1. Python 측에서 Bridge.call("track_pose", x, y, vis, should_track) 호출
 *   2. should_track == true: 데드존 밖이면 target_camera_angle 업데이트
 *   3. should_track == false: target 업데이트 안 함 (현재 위치 유지 = STOP)
 *   4. loop(): PID로 current → target 보간 → 서보 write
 *   5. LED ring: visibility 0~1 → 색상 (적색 낮음 / 녹색 높음) 표시
 *
 * 기반: ShawnHymel/face-expression-detection-robot (MIT, 2025 Shawn Hymel)
 *   https://github.com/ShawnHymel/face-expression-detection-robot
 * 변경: animate_head() → track_pose(), 표정 LED 7클래스 → visibility 색상
 */

#include "Arduino_RouterBridge.h"
#include "Servo.h"
#include "ws2812b-bitbang.h"

// Servo settings (Shawn 원본 게인 그대로)
#define DEBUG           1
#define PAN_SERVO_PIN   9
#define TILT_SERVO_PIN  10
#define PAN_MIN         0
#define PAN_MAX         180
#define TILT_MIN        0
#define TILT_MAX        180
#define HORIZONTAL_FOV  60      // SU200 카메라 FOV 측정 후 수정 가능
#define VERTICAL_FOV    30
#define X_CENTER        0.5
#define Y_CENTER        0.5
#define X_DEAD_ZONE     0.08
#define Y_DEAD_ZONE     0.08
#define PAN_DIR         -1
#define TILT_DIR        1
#define DELAY_MS        50

// PID (Shawn 검증된 게인 그대로)
#define PAN_KP          0.15
#define PAN_KI          0.005
#define PAN_KD          0.005
#define PAN_I_MAX       10.0
#define TILT_KP         0.5
#define TILT_KI         0.005
#define TILT_KD         0.005
#define TILT_I_MAX      10.0

// LED ring — visibility 점수 표시 (12 LED)
#define NUM_LEDS                12
#define LED_RING_TIMEOUT_MS     2000

// Derived
#define PAN_CENTER      (((PAN_MAX - PAN_MIN) / 2) + PAN_MIN)
#define TILT_CENTER     (((TILT_MAX - TILT_MIN) / 2) + TILT_MIN)

// Servo objects
Servo pan_servo;
Servo tilt_servo;

// Global angles
float current_pan = PAN_CENTER;
float current_tilt = TILT_CENTER;
float current_camera_angle_x = 0.0;
volatile float target_camera_angle_x = 0.0;
float current_camera_angle_y = 0.0;
volatile float target_camera_angle_y = 0.0;

// PID state
float pan_integral = 0.0;
float pan_last_error = 0.0;
float tilt_integral = 0.0;
float tilt_last_error = 0.0;

// Visibility tracking
volatile float last_visibility = 0.0;
volatile bool last_should_track = false;
unsigned long last_call_ms = 0;

// LED framebuffer
uint8_t framebuffer[NUM_LEDS][4];
bool led_ring_active = false;

// Debug
#if DEBUG
# define debug(fmt, ...) do { char buf[256]; snprintf(buf, sizeof(buf), fmt, ##__VA_ARGS__); Serial.print(buf); } while(0)
#else
# define debug(fmt, ...)
#endif

/*******************************************************************************
 * PID controller
 */
float pid_update(float error, float *integral, float *last_error,
                 float kp, float ki, float kd, float i_max, float dt) {
    float p_term = kp * error;
    *integral += error * dt;
    if (*integral > i_max)  *integral = i_max;
    if (*integral < -i_max) *integral = -i_max;
    float i_term = ki * (*integral);
    float derivative = (error - *last_error) / dt;
    float d_term = kd * derivative;
    *last_error = error;
    return p_term + i_term + d_term;
}

/*******************************************************************************
 * LED ring — visibility 색상 표시
 *   - vis < 0.3 : 적색 (검출 매우 낮음)
 *   - 0.3 ≤ vis < 0.7 : 노랑 (추적 중)
 *   - vis ≥ 0.7 : 녹색 (STAY, 카운팅 가능)
 */
void set_led_visibility(float visibility) {
    uint8_t g = 0, r = 0;
    if (visibility < 0.3) {
        r = 0xFF;  // 적
    } else if (visibility < 0.7) {
        r = 0xFF;  // 노랑 = R + G
        g = 0xFF;
    } else {
        g = 0xFF;  // 녹
    }
    for (int i = 0; i < NUM_LEDS; i++) {
        framebuffer[i][0] = g;
        framebuffer[i][1] = r;
        framebuffer[i][2] = 0;
        framebuffer[i][3] = 0;
    }
    ws2812b_show(framebuffer, NUM_LEDS);
    led_ring_active = true;
}

void set_led_off() {
    for (int i = 0; i < NUM_LEDS; i++) {
        framebuffer[i][0] = 0;
        framebuffer[i][1] = 0;
        framebuffer[i][2] = 0;
        framebuffer[i][3] = 0;
    }
    ws2812b_show(framebuffer, NUM_LEDS);
    led_ring_active = false;
}

/*******************************************************************************
 * Bridge callback: Python에서 호출
 *   x_norm, y_norm    : 사람 중심점 정규화 좌표 (0~1)
 *   visibility        : 0~1 score (무릎 가중치 큰 평균 conf)
 *   should_track      : true면 추적, false면 STAY
 */
void track_pose(float x_norm, float y_norm, float visibility, bool should_track) {
    last_call_ms = millis();
    last_visibility = visibility;
    last_should_track = should_track;

    debug("Pose: (%.2f, %.2f) vis=%.2f track=%d\r\n",
          x_norm, y_norm, visibility, should_track ? 1 : 0);

    // LED 색상 갱신 (항상)
    set_led_visibility(visibility);

    // STAY 모드 — target 업데이트 X (현재 위치 유지)
    if (!should_track) {
        debug("  STAY (visibility >= track threshold)\r\n");
        return;
    }

    // TRACK 모드 — 데드존 밖이면 target 업데이트 (Shawn 원본 로직)
    float x_error = x_norm - X_CENTER;
    float y_error = y_norm - Y_CENTER;
    float face_angle, target_servo;

    if (fabs(x_error) > X_DEAD_ZONE) {
        face_angle = x_error * HORIZONTAL_FOV;
        target_camera_angle_x = current_camera_angle_x + (PAN_DIR * face_angle);
        target_servo = PAN_CENTER + target_camera_angle_x;
        if (target_servo < PAN_MIN)      target_camera_angle_x = PAN_MIN - PAN_CENTER;
        else if (target_servo > PAN_MAX) target_camera_angle_x = PAN_MAX - PAN_CENTER;
    }

    if (fabs(y_error) > Y_DEAD_ZONE) {
        face_angle = y_error * VERTICAL_FOV;
        target_camera_angle_y = current_camera_angle_y + (TILT_DIR * face_angle);
        target_servo = TILT_CENTER + target_camera_angle_y;
        if (target_servo < TILT_MIN)       target_camera_angle_y = TILT_MIN - TILT_CENTER;
        else if (target_servo > TILT_MAX)  target_camera_angle_y = TILT_MAX - TILT_CENTER;
    }
}

/*******************************************************************************
 * setup / loop
 */
void setup() {
#if DEBUG
    Serial.begin(115200);
#endif
    ws2812b_init();
    Bridge.begin();
    Bridge.provide("track_pose", track_pose);

    pan_servo.attach(PAN_SERVO_PIN);
    tilt_servo.attach(TILT_SERVO_PIN);
    pan_servo.write(current_pan);
    tilt_servo.write(current_tilt);

    debug("PTZ PoC sketch ready\r\n");
}

void loop() {
    float dt = DELAY_MS / 1000.0;

    // PID — current → target 보간 (Shawn 원본 그대로)
    float camera_error_x = target_camera_angle_x - current_camera_angle_x;
    float camera_error_y = target_camera_angle_y - current_camera_angle_y;

    float camera_delta_x = pid_update(
        camera_error_x, &pan_integral, &pan_last_error,
        PAN_KP, PAN_KI, PAN_KD, PAN_I_MAX, dt
    );
    float camera_delta_y = pid_update(
        camera_error_y, &tilt_integral, &tilt_last_error,
        TILT_KP, TILT_KI, TILT_KD, TILT_I_MAX, dt
    );

    // Velocity profile X
    float em = fabs(camera_error_x);
    float scale = (em > 10.0) ? 1.0 : 0.1 + 0.9 * (em / 10.0) * (em / 10.0);
    current_camera_angle_x += scale * camera_delta_x;

    // Velocity profile Y
    em = fabs(camera_error_y);
    scale = (em > 10.0) ? 1.0 : 0.1 + 0.9 * (em / 10.0) * (em / 10.0);
    current_camera_angle_y += scale * camera_delta_y;

    // Convert to servo angle
    current_pan = PAN_CENTER + current_camera_angle_x;
    current_tilt = TILT_CENTER + current_camera_angle_y;
    current_pan = min(max(current_pan, (float)PAN_MIN), (float)PAN_MAX);
    current_tilt = min(max(current_tilt, (float)TILT_MIN), (float)TILT_MAX);
    current_camera_angle_x = current_pan - PAN_CENTER;
    current_camera_angle_y = current_tilt - TILT_CENTER;

    pan_servo.write((int)current_pan);
    tilt_servo.write((int)current_tilt);

    // LED 타임아웃 (사람 미검출 N초 후 LED off)
    if (led_ring_active && (millis() - last_call_ms > LED_RING_TIMEOUT_MS)) {
        set_led_off();
    }

    delay(DELAY_MS);
}
