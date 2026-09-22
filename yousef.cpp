/*
===========================================================
        MMRC26 MICROMOUSE - ESP32
        10 x 10 MAZE - FLOOD FILL
===========================================================

الفكرة العامة:

1) SEARCH RUN
   - الروبوت يبدأ من Corner.
   - يقرأ الجدران باستخدام 3 TOF.
   - يبني Map داخل الذاكرة.
   - يستخدم Flood Fill لاختيار الاتجاه.
   - يصل إلى الـ Center Goal.

2) SPEED RUN
   - يستخدم الـ Map التي بناها في Search Run.
   - يحسب أقصر مسار للـ Center.
   - ينفذ المسار بسرعة أعلى.

ملاحظات مهمة:
- لا يوجد Maze Layout مكتوب مسبقاً داخل الكود.
- الروبوت يتعلم المتاهة من Sensors.
- هذا مهم لأن Rulebook يمنع إدخال معلومات المتاهة
  بعد الكشف عنها.
- الـ Maze = 10x10.
- Cell = 180 mm.
- Goal = الأربع خلايا في المركز.

===========================================================
*/


#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>


// =========================================================
// 1. MOTOR PINS
// =========================================================
//
// كل موتور عنده:
// PWM  -> السرعة
// DIR  -> اتجاه الدوران
//
// إذا اتجاه موتور عندك معكوس، عدل MOTOR_LEFT_REVERSE
// أو MOTOR_RIGHT_REVERSE بالأسفل.
// =========================================================

#define PIN_MOTOR_LEFT_PWM    25
#define PIN_MOTOR_LEFT_DIR    26

#define PIN_MOTOR_RIGHT_PWM   27
#define PIN_MOTOR_RIGHT_DIR   14


// =========================================================
// 2. I2C PINS
// =========================================================
//
// I2C0:
//   Left AS5600
//
// I2C1:
//   Right AS5600
//   3x VL53L0X
//
// ملاحظة:
// الـ VL53L0X الثلاثة لهم نفس I2C Address في البداية،
// لذلك نستخدم XSHUT لإعطاء كل Sensor Address مختلف.
// =========================================================

#define I2C0_SDA 21
#define I2C0_SCL 22

#define I2C1_SDA 18
#define I2C1_SCL 19


// =========================================================
// 3. AS5600
// =========================================================

#define AS5600_ADDR 0x36

#define AS5600_RAW_ANGLE_HIGH 0x0E


// =========================================================
// 4. VL53L0X XSHUT PINS
// =========================================================
//
// كل Sensor يبدأ OFF.
// نشغلهم واحداً واحداً ونغير الـ Address.
// =========================================================

#define XSHUT_FRONT 23
#define XSHUT_LEFT  32
#define XSHUT_RIGHT 33


// =========================================================
// 5. MAZE CONSTANTS
// =========================================================
//
// Rulebook:
// Maze = 10 x 10
// Cell = 18cm x 18cm
//
// لذلك:
// CELL_SIZE_MM = 180
// =========================================================

#define MAZE_SIZE 10

const float CELL_SIZE_MM = 180.0;


// =========================================================
// 6. ROBOT MECHANICAL CONSTANTS
// =========================================================
//
// هذه القيم يجب Calibration عليها فعلياً.
// =========================================================

const float WHEEL_DIAMETER_MM = 32.0;
const float WHEEL_BASE_MM     = 70.0;

const float COUNTS_PER_REV = 4096.0;


// =========================================================
// 7. MOTOR CONTROL
// =========================================================

#define PWM_FREQUENCY 20000
#define PWM_RESOLUTION 8

#define MAX_PWM 255


// سرعة Search.
// خليها منخفضة بالبداية للتجارب.

#define SEARCH_SPEED 110


// سرعة Speed Run.
// لا تعتبر هذه القيمة "Maximum Speed" مباشرة.
// لازم تعمل Calibration للروبوت.

#define SPEED_RUN_SPEED 190


// سرعة الدوران.

#define TURN_SPEED 100


// =========================================================
// 8. MOTOR DIRECTION CALIBRATION
// =========================================================
//
// إذا أحد الموتورات يتحرك بالعكس:
// غير true / false.
//
// مثال:
// left صحيح
// right معكوس
//
// MOTOR_RIGHT_REVERSE = true
// =========================================================

bool MOTOR_LEFT_REVERSE  = false;
bool MOTOR_RIGHT_REVERSE = false;


// =========================================================
// 9. START POSITION
// =========================================================
//
// هذا يحدد Corner الذي يوضع فيه الروبوت.
//
// الافتراضي:
// Bottom-Left
// x = 0
// y = 9
//
// Facing NORTH.
//
// إذا وضعتم الروبوت في Corner مختلف، يتم تعديل
// نقطة البداية واتجاه البداية فقط.
//
// لا يوجد أي Maze Wall Layout هنا.
// =========================================================

int startX = 0;
int startY = 9;


// =========================================================
// 10. DIRECTIONS
// =========================================================
//
// North = 0
// East  = 1
// South = 2
// West  = 3
//
// الاتجاهات Clockwise.
// =========================================================

enum Direction
{
  NORTH = 0,
  EAST  = 1,
  SOUTH = 2,
  WEST  = 3
};


// =========================================================
// 11. ROBOT CURRENT STATE
// =========================================================

struct RobotState
{
  int x;
  int y;

  Direction dir;
};


// الروبوت يبدأ من الـ Start.

RobotState robot;


// =========================================================
// 12. MAZE WALL REPRESENTATION
// =========================================================
//
// كل Cell لها 4 Walls:
//
// bit 0 = NORTH
// bit 1 = EAST
// bit 2 = SOUTH
// bit 3 = WEST
//
// مثال:
//
// 0001 = North Wall
// 0011 = North + East
//
// =========================================================

#define WALL_NORTH (1 << 0)
#define WALL_EAST  (1 << 1)
#define WALL_SOUTH (1 << 2)
#define WALL_WEST  (1 << 3)


// =========================================================
// 13. KNOWN WALLS
// =========================================================
//
// مهم جداً:
//
// walls[][]
// يخزن الجدران التي نعرف أنها موجودة.
//
// known[][]
// يخزن أي Directions قمنا بفحصها.
//
// السبب:
// في بداية Search Run لا نعرف المتاهة.
// =========================================================

uint8_t walls[MAZE_SIZE][MAZE_SIZE];

uint8_t knownWalls[MAZE_SIZE][MAZE_SIZE];


// =========================================================
// 14. FLOOD FILL VALUES
// =========================================================
//
// flood[y][x]
// = عدد الخطوات التقريبية للوصول للـ Goal.
//
// يتم حسابها باستخدام BFS.
//
// الهدف:
// الخلايا الأربع في المركز = 0
//
// =========================================================

uint16_t flood[MAZE_SIZE][MAZE_SIZE];


// =========================================================
// 15. GOAL CELLS
// =========================================================
//
// 10x10:
//
// الوسط هو:
//
// (4,4)
// (5,4)
// (4,5)
// (5,5)
//
// هذه الأربع خلايا هي Destination Zone.
// =========================================================

bool isGoalCell(int x, int y)
{
  return
    (x == 4 && y == 4) ||
    (x == 5 && y == 4) ||
    (x == 4 && y == 5) ||
    (x == 5 && y == 5);
}


// =========================================================
// 16. I2C OBJECTS
// =========================================================

TwoWire I2C_LEFT  = TwoWire(0);
TwoWire I2C_RIGHT = TwoWire(1);


// =========================================================
// 17. TOF OBJECTS
// =========================================================

VL53L0X tofFront;
VL53L0X tofLeft;
VL53L0X tofRight;


// =========================================================
// 18. SENSOR DISTANCE THRESHOLDS
// =========================================================
//
// هذه القيم يجب Calibration عليها.
//
// إذا المسافة أقل من WALL_THRESHOLD
// نعتبر أن هناك Wall.
//
// =========================================================

const uint16_t WALL_THRESHOLD_MM = 110;


// =========================================================
// 19. AS5600 ENCODER STATE
// =========================================================

struct EncoderState
{
  uint16_t previousRaw;

  long totalTicks;

  bool initialized;
};


EncoderState leftEncoder;
EncoderState rightEncoder;


// =========================================================
// 20. READ AS5600 RAW ANGLE
// =========================================================
//
// AS5600 يعطي زاوية 12-bit:
//
// 0 -> 4095
//
// نستخدمها لحساب مقدار دوران العجلة.
// =========================================================

uint16_t readAS5600(TwoWire &bus)
{
  bus.beginTransmission(AS5600_ADDR);
  bus.write(AS5600_RAW_ANGLE_HIGH);

  if (bus.endTransmission(false) != 0)
  {
    return 0;
  }

  bus.requestFrom(AS5600_ADDR, 2);

  if (bus.available() < 2)
  {
    return 0;
  }

  uint16_t high = bus.read();
  uint16_t low  = bus.read();

  return ((high << 8) | low) & 0x0FFF;
}


// =========================================================
// 21. ENCODER UPDATE
// =========================================================
//
// AS5600 لا يعطي Tick Counter مباشر.
// هو يعطي زاوية Absolute.
//
// لذلك نحسب الفرق بين القراءة الحالية والسابقة.
// ونتعامل مع الـ 12-bit Wrap Around.
//
// مثال:
//
// 4090 -> 5
//
// هذا ليس فرق -4085.
// بل تقريباً +11.
// =========================================================

long angleDifference(uint16_t current, uint16_t previous)
{
  long diff = (long)current - (long)previous;

  if (diff > 2048)
  {
    diff -= 4096;
  }

  if (diff < -2048)
  {
    diff += 4096;
  }

  return diff;
}


void updateEncoders()
{
  uint16_t leftRaw  = readAS5600(I2C_LEFT);
  uint16_t rightRaw = readAS5600(I2C_RIGHT);


  // أول قراءة فقط للتأسيس.

  if (!leftEncoder.initialized)
  {
    leftEncoder.previousRaw = leftRaw;
    leftEncoder.initialized = true;
  }

  if (!rightEncoder.initialized)
  {
    rightEncoder.previousRaw = rightRaw;
    rightEncoder.initialized = true;
  }


  // حساب الفرق.

  long leftDiff =
    angleDifference(leftRaw, leftEncoder.previousRaw);

  long rightDiff =
    angleDifference(rightRaw, rightEncoder.previousRaw);


  // إضافة الفرق إلى Total Ticks.

  leftEncoder.totalTicks += leftDiff;

  rightEncoder.totalTicks += rightDiff;


  // تحديث القراءة السابقة.

  leftEncoder.previousRaw  = leftRaw;
  rightEncoder.previousRaw = rightRaw;
}


// =========================================================
// 22. RESET ENCODERS
// =========================================================

void resetEncoders()
{
  uint16_t leftRaw  = readAS5600(I2C_LEFT);
  uint16_t rightRaw = readAS5600(I2C_RIGHT);


  leftEncoder.previousRaw = leftRaw;
  leftEncoder.totalTicks  = 0;
  leftEncoder.initialized = true;


  rightEncoder.previousRaw = rightRaw;
  rightEncoder.totalTicks  = 0;
  rightEncoder.initialized = true;
}


// =========================================================
// 23. TICKS -> MILLIMETERS
// =========================================================
//
// دورة كاملة للعجلة:
//
// circumference = PI * diameter
//
// AS5600:
//
// 4096 counts/revolution
//
// لذلك نحول ticks إلى mm.
// =========================================================

float ticksToMM(long ticks)
{
  float wheelCircumference =
    PI * WHEEL_DIAMETER_MM;

  return
    ((float)ticks / COUNTS_PER_REV)
    * wheelCircumference;
}


// =========================================================
// 24. MOTOR CONTROL
// =========================================================
//
// speed:
//
// +255 = forward
// -255 = reverse
//  0   = stop
// =========================================================

void setMotor(int leftSpeed, int rightSpeed)
{
  leftSpeed  = constrain(leftSpeed, -MAX_PWM, MAX_PWM);
  rightSpeed = constrain(rightSpeed, -MAX_PWM, MAX_PWM);


  // Left motor direction.

  bool leftForward = leftSpeed >= 0;

  if (MOTOR_LEFT_REVERSE)
  {
    leftForward = !leftForward;
  }


  // Right motor direction.

  bool rightForward = rightSpeed >= 0;

  if (MOTOR_RIGHT_REVERSE)
  {
    rightForward = !rightForward;
  }


  digitalWrite(
    PIN_MOTOR_LEFT_DIR,
    leftForward ? HIGH : LOW
  );

  digitalWrite(
    PIN_MOTOR_RIGHT_DIR,
    rightForward ? HIGH : LOW
  );


  // PWM values.

  analogWrite(
    PIN_MOTOR_LEFT_PWM,
    abs(leftSpeed)
  );

  analogWrite(
    PIN_MOTOR_RIGHT_PWM,
    abs(rightSpeed)
  );
}


// =========================================================
// 25. STOP MOTORS
// =========================================================

void stopMotors()
{
  analogWrite(PIN_MOTOR_LEFT_PWM, 0);
  analogWrite(PIN_MOTOR_RIGHT_PWM, 0);
}


// =========================================================
// 26. SETUP MOTOR PINS
// =========================================================

void setupMotors()
{
  pinMode(PIN_MOTOR_LEFT_PWM, OUTPUT);
  pinMode(PIN_MOTOR_LEFT_DIR, OUTPUT);

  pinMode(PIN_MOTOR_RIGHT_PWM, OUTPUT);
  pinMode(PIN_MOTOR_RIGHT_DIR, OUTPUT);

  stopMotors();
}


// =========================================================
// 27. INITIALIZE TOF SENSORS
// =========================================================
//
// الثلاثة VL53L0X يبدأون بنفس الـ Address.
//
// لذلك:
//
// 1) نطفئ الجميع.
// 2) نشغل Front -> نعطيه Address 0x30
// 3) نشغل Left  -> نعطيه Address 0x31
// 4) نشغل Right -> نعطيه Address 0x32
//
// =========================================================

bool setupTOF()
{
  pinMode(XSHUT_FRONT, OUTPUT);
  pinMode(XSHUT_LEFT, OUTPUT);
  pinMode(XSHUT_RIGHT, OUTPUT);


  // إطفاء جميع الحساسات.

  digitalWrite(XSHUT_FRONT, LOW);
  digitalWrite(XSHUT_LEFT, LOW);
  digitalWrite(XSHUT_RIGHT, LOW);

  delay(20);


  // -------------------------------------------------------
  // FRONT
  // -------------------------------------------------------

  digitalWrite(XSHUT_FRONT, HIGH);
  delay(20);

  if (!tofFront.init())
  {
    Serial.println("ERROR: Front TOF failed");
    return false;
  }

  tofFront.setAddress(0x30);

  tofFront.setTimeout(50);


  // -------------------------------------------------------
  // LEFT
  // -------------------------------------------------------

  digitalWrite(XSHUT_LEFT, HIGH);
  delay(20);

  if (!tofLeft.init())
  {
    Serial.println("ERROR: Left TOF failed");
    return false;
  }

  tofLeft.setAddress(0x31);

  tofLeft.setTimeout(50);


  // -------------------------------------------------------
  // RIGHT
  // -------------------------------------------------------

  digitalWrite(XSHUT_RIGHT, HIGH);
  delay(20);

  if (!tofRight.init())
  {
    Serial.println("ERROR: Right TOF failed");
    return false;
  }

  tofRight.setAddress(0x32);

  tofRight.setTimeout(50);


  // -------------------------------------------------------
  // Start continuous measurement.
  // -------------------------------------------------------

  tofFront.startContinuous();
  tofLeft.startContinuous();
  tofRight.startContinuous();


  Serial.println("TOF sensors ready.");

  return true;
}


// =========================================================
// 28. READ DISTANCE
// =========================================================

uint16_t readFrontDistance()
{
  return tofFront.readRangeContinuousMillimeters();
}


uint16_t readLeftDistance()
{
  return tofLeft.readRangeContinuousMillimeters();
}


uint16_t readRightDistance()
{
  return tofRight.readRangeContinuousMillimeters();
}


// =========================================================
// 29. CHECK WALL
// =========================================================

bool frontWall()
{
  uint16_t distance = readFrontDistance();

  if (tofFront.timeoutOccurred())
  {
    return true;
  }

  return distance < WALL_THRESHOLD_MM;
}


bool leftWall()
{
  uint16_t distance = readLeftDistance();

  if (tofLeft.timeoutOccurred())
  {
    return true;
  }

  return distance < WALL_THRESHOLD_MM;
}


bool rightWall()
{
  uint16_t distance = readRightDistance();

  if (tofRight.timeoutOccurred())
  {
    return true;
  }

  return distance < WALL_THRESHOLD_MM;
}


// =========================================================
// 30. DIRECTION HELPERS
// =========================================================

Direction turnLeftDirection(Direction d)
{
  return (Direction)((d + 3) % 4);
}


Direction turnRightDirection(Direction d)
{
  return (Direction)((d + 1) % 4);
}


Direction turnBackDirection(Direction d)
{
  return (Direction)((d + 2) % 4);
}


// =========================================================
// 31. GET WALL BIT
// =========================================================

uint8_t directionToWallBit(Direction d)
{
  switch (d)
  {
    case NORTH:
      return WALL_NORTH;

    case EAST:
      return WALL_EAST;

    case SOUTH:
      return WALL_SOUTH;

    case WEST:
      return WALL_WEST;
  }

  return 0;
}


// =========================================================
// 32. GET NEIGHBOR CELL
// =========================================================

bool getNeighbor(
  int x,
  int y,
  Direction d,
  int &nx,
  int &ny
)
{
  nx = x;
  ny = y;


  switch (d)
  {
    case NORTH:
      ny--;
      break;

    case EAST:
      nx++;
      break;

    case SOUTH:
      ny++;
      break;

    case WEST:
      nx--;
      break;
  }


  // خارج المتاهة = Wall.

  if (nx < 0 || nx >= MAZE_SIZE ||
      ny < 0 || ny >= MAZE_SIZE)
  {
    return false;
  }


  return true;
}


// =========================================================
// 33. SET WALL
// =========================================================
//
// عندما نعرف أن هناك Wall:
//
// current cell -> Wall
// neighbor cell -> Wall
//
// هذا يجعل الـ Map متناسقاً.
// =========================================================

void setWall(
  int x,
  int y,
  Direction d,
  bool hasWall
)
{
  if (x < 0 || x >= MAZE_SIZE ||
      y < 0 || y >= MAZE_SIZE)
  {
    return;
  }


  uint8_t bit = directionToWallBit(d);


  // Direction أصبحت Known.

  knownWalls[y][x] |= bit;


  if (hasWall)
  {
    walls[y][x] |= bit;
  }
  else
  {
    walls[y][x] &= ~bit;
  }


  // -------------------------------------------------------
  // تحديث الـ Neighbor أيضاً.
  // -------------------------------------------------------

  int nx;
  int ny;


  if (getNeighbor(x, y, d, nx, ny))
  {
    Direction opposite =
      turnBackDirection(d);

    uint8_t oppositeBit =
      directionToWallBit(opposite);


    knownWalls[ny][nx] |= oppositeBit;


    if (hasWall)
    {
      walls[ny][nx] |= oppositeBit;
    }
    else
    {
      walls[ny][nx] &= ~oppositeBit;
    }
  }
}


// =========================================================
// 34. READ CURRENT CELL WALLS
// =========================================================
//
// لدينا 3 Sensors:
//
// Front
// Left
// Right
//
// بالنسبة للـ Back:
// غالباً يكون معروفاً من الـ Neighbor الذي أتينا منه.
//
// إذا كان Unknown، سيتم فحصه عند الحاجة.
// =========================================================

void senseCurrentCell()
{
  bool front = frontWall();
  bool left  = leftWall();
  bool right = rightWall();


  // Front بالنسبة للاتجاه الحالي.

  setWall(
    robot.x,
    robot.y,
    robot.dir,
    front
  );


  // Left.

  Direction leftDir =
    turnLeftDirection(robot.dir);

  setWall(
    robot.x,
    robot.y,
    leftDir,
    left
  );


  // Right.

  Direction rightDir =
    turnRightDirection(robot.dir);

  setWall(
    robot.x,
    robot.y,
    rightDir,
    right
  );
}


// =========================================================
// 35. INITIALIZE MAZE MAP
// =========================================================

void initializeMaze()
{
  for (int y = 0; y < MAZE_SIZE; y++)
  {
    for (int x = 0; x < MAZE_SIZE; x++)
    {
      walls[y][x] = 0;

      knownWalls[y][x] = 0;

      flood[y][x] = 65535;
    }
  }


  // -------------------------------------------------------
  // الجدران الخارجية معروفة من هندسة المتاهة.
  //
  // هذا ليس Maze Layout.
  // هو حدود المتاهة الخارجية فقط.
  // -------------------------------------------------------

  for (int x = 0; x < MAZE_SIZE; x++)
  {
    setWall(x, 0, NORTH, true);
    setWall(x, MAZE_SIZE - 1, SOUTH, true);
  }


  for (int y = 0; y < MAZE_SIZE; y++)
  {
    setWall(0, y, WEST, true);
    setWall(MAZE_SIZE - 1, y, EAST, true);
  }
}


// =========================================================
// 36. FLOOD FILL
// =========================================================
//
// BFS من الأربع Goal Cells.
//
// الهدف:
// إعطاء كل Cell قيمة تمثل أقصر عدد خطوات معروف
// للوصول إلى Goal.
//
// في Search Run:
// الجدران غير المعروفة تعتبر مؤقتاً غير مغلقة
// حتى يتم استكشافها.
// لكن قبل أي حركة يتم فحص الاتجاه فعلياً.
// =========================================================

void calculateFloodFill()
{
  const int MAX_CELLS =
    MAZE_SIZE * MAZE_SIZE;


  int queueX[MAX_CELLS];
  int queueY[MAX_CELLS];


  int head = 0;
  int tail = 0;


  // -------------------------------------------------------
  // Reset.
  // -------------------------------------------------------

  for (int y = 0; y < MAZE_SIZE; y++)
  {
    for (int x = 0; x < MAZE_SIZE; x++)
    {
      flood[y][x] = 65535;
    }
  }


  // -------------------------------------------------------
  // Goal Cells = 0
  // -------------------------------------------------------

  flood[4][4] = 0;
  queueX[tail] = 4;
  queueY[tail] = 4;
  tail++;


  flood[5][4] = 0;
  queueX[tail] = 5;
  queueY[tail] = 4;
  tail++;


  flood[4][5] = 0;
  queueX[tail] = 4;
  queueY[tail] = 5;
  tail++;


  flood[5][5] = 0;
  queueX[tail] = 5;
  queueY[tail] = 5;
  tail++;


  // -------------------------------------------------------
  // BFS.
  // -------------------------------------------------------

  while (head < tail)
  {
    int x = queueX[head];
    int y = queueY[head];

    head++;


    uint16_t currentValue =
      flood[y][x];


    for (int d = 0; d < 4; d++)
    {
      Direction dir =
        (Direction)d;


      int nx;
      int ny;


      if (!getNeighbor(
            x,
            y,
            dir,
            nx,
            ny))
      {
        continue;
      }


      // ---------------------------------------------------
      // إذا الجدار معروف وموجود:
      // لا نستطيع المرور.
      // ---------------------------------------------------

      uint8_t bit =
        directionToWallBit(dir);


      if ((knownWalls[y][x] & bit) &&
          (walls[y][x] & bit))
      {
        continue;
      }


      // ---------------------------------------------------
      // إذا لم يكن معروفاً، نسمح له مؤقتاً.
      // Sensor سيؤكد ذلك قبل الحركة.
      // ---------------------------------------------------

      uint16_t newValue =
        currentValue + 1;


      if (newValue < flood[ny][nx])
      {
        flood[ny][nx] = newValue;

        queueX[tail] = nx;
        queueY[tail] = ny;

        tail++;
      }
    }
  }
}


// =========================================================
// 37. CHECK IF DIRECTION HAS KNOWN WALL
// =========================================================

bool isKnownWall(Direction d)
{
  uint8_t bit =
    directionToWallBit(d);

  return
    (knownWalls[robot.y][robot.x] & bit) &&
    (walls[robot.y][robot.x] & bit);
}


// =========================================================
// 38. CHECK IF DIRECTION IS KNOWN OPEN
// =========================================================

bool isKnownOpen(Direction d)
{
  uint8_t bit =
    directionToWallBit(d);

  return
    (knownWalls[robot.y][robot.x] & bit) &&
    !(walls[robot.y][robot.x] & bit);
}


// =========================================================
// 39. GET FLOOD VALUE OF NEIGHBOR
// =========================================================

uint16_t getNeighborFlood(Direction d)
{
  int nx;
  int ny;


  if (!getNeighbor(
        robot.x,
        robot.y,
        d,
        nx,
        ny))
  {
    return 65535;
  }


  return flood[ny][nx];
}


// =========================================================
// 40. SELECT NEXT DIRECTION
// =========================================================
//
// Flood Fill chooses the neighbor with the lowest flood value.
//
// Priority:
//
// 1) lowest Flood Value
// 2) prefer Forward
// 3) then Left
// 4) then Right
// 5) then Back
//
// لكن أي Direction فيه Wall معروف يتم استبعاده.
//
// الاتجاه Unknown مسموح مؤقتاً.
// قبل الحركة يتم التأكد من الـ TOF.
// =========================================================

Direction chooseNextDirection()
{
  Direction candidates[4] =
  {
    robot.dir,
    turnLeftDirection(robot.dir),
    turnRightDirection(robot.dir),
    turnBackDirection(robot.dir)
  };


  Direction bestDirection =
    robot.dir;

  uint16_t bestValue =
    65535;


  for (int i = 0; i < 4; i++)
  {
    Direction d =
      candidates[i];


    // إذا Wall معروف -> ممنوع.

    if (isKnownWall(d))
    {
      continue;
    }


    uint16_t value =
      getNeighborFlood(d);


    if (value < bestValue)
    {
      bestValue = value;

      bestDirection = d;
    }
  }


  return bestDirection;
}


// =========================================================
// 41. TURN LEFT 90
// =========================================================
//
// نحسب المسافة التي يجب أن تقطعها كل عجلة:
//
// Arc = PI * WheelBase / 4
//
// إحدى العجلات Forward
// الثانية Reverse
//
// هذه القيمة تحتاج Calibration عملياً.
// =========================================================

void turnLeft90()
{
  resetEncoders();


  float targetDistance =
    PI * WHEEL_BASE_MM / 4.0;


  setMotor(
    -TURN_SPEED,
     TURN_SPEED
  );


  while (true)
  {
    updateEncoders();


    float leftDistance =
      abs(ticksToMM(leftEncoder.totalTicks));


    float rightDistance =
      abs(ticksToMM(rightEncoder.totalTicks));


    float average =
      (leftDistance + rightDistance) / 2.0;


    if (average >= targetDistance)
    {
      break;
    }


    delay(2);
  }


  stopMotors();

  delay(40);


  robot.dir =
    turnLeftDirection(robot.dir);
}


// =========================================================
// 42. TURN RIGHT 90
// =========================================================

void turnRight90()
{
  resetEncoders();


  float targetDistance =
    PI * WHEEL_BASE_MM / 4.0;


  setMotor(
     TURN_SPEED,
    -TURN_SPEED
  );


  while (true)
  {
    updateEncoders();


    float leftDistance =
      abs(ticksToMM(leftEncoder.totalTicks));


    float rightDistance =
      abs(ticksToMM(rightEncoder.totalTicks));


    float average =
      (leftDistance + rightDistance) / 2.0;


    if (average >= targetDistance)
    {
      break;
    }


    delay(2);
  }


  stopMotors();

  delay(40);


  robot.dir =
    turnRightDirection(robot.dir);
}


// =========================================================
// 43. TURN 180
// =========================================================

void turn180()
{
  turnRight90();
  turnRight90();
}


// =========================================================
// 44. TURN TO TARGET DIRECTION
// =========================================================
//
// نحدد الفرق بين الاتجاه الحالي والمطلوب.
// =========================================================

void turnTo(Direction target)
{
  int current =
    (int)robot.dir;

  int wanted =
    (int)target;


  int difference =
    (wanted - current + 4) % 4;


  if (difference == 0)
  {
    return;
  }


  if (difference == 1)
  {
    turnRight90();
  }
  else if (difference == 2)
  {
    turn180();
  }
  else if (difference == 3)
  {
    turnLeft90();
  }
}


// =========================================================
// 45. VERIFY FRONT BEFORE MOVING
// =========================================================
//
// حتى لو Flood Fill قال إن الطريق مفتوح،
// لا نتحرك بدون فحص TOF.
//
// إذا وجدنا Wall:
// نسجلها في Map
// ونرجع نحسب Flood Fill.
// =========================================================

bool verifyFrontOpen()
{
  uint16_t distance =
    readFrontDistance();


  if (tofFront.timeoutOccurred())
  {
    return false;
  }


  bool blocked =
    distance < WALL_THRESHOLD_MM;


  setWall(
    robot.x,
    robot.y,
    robot.dir,
    blocked
  );


  return !blocked;
}


// =========================================================
// 46. MOVE ONE CELL
// =========================================================
//
// Cell = 180mm.
//
// نستخدم Encoder feedback.
//
// يوجد P correction بسيط للحفاظ على
// أن العجلتين تقطعان مسافة متقاربة.
//
// هذه ليست PID كاملة.
// =========================================================

bool moveOneCell(int baseSpeed)
{
  // -------------------------------------------------------
  // Safety check.
  // -------------------------------------------------------

  if (!verifyFrontOpen())
  {
    stopMotors();

    return false;
  }


  // -------------------------------------------------------
  // Reset encoder distance.
  // -------------------------------------------------------

  resetEncoders();


  const float target =
    CELL_SIZE_MM;


  const float Kp =
    1.0;


  while (true)
  {
    updateEncoders();


    float leftDistance =
      ticksToMM(leftEncoder.totalTicks);


    float rightDistance =
      ticksToMM(rightEncoder.totalTicks);


    float averageDistance =
      (abs(leftDistance) +
       abs(rightDistance)) / 2.0;


    // -----------------------------------------------------
    // انتهت الخلية.
    // -----------------------------------------------------

    if (averageDistance >= target)
    {
      break;
    }


    // -----------------------------------------------------
    // Wheel synchronization.
    //
    // إذا اليسار قطع أكثر:
    // نقلل سرعته قليلاً.
    //
    // إذا اليمين قطع أكثر:
    // نقلل سرعته قليلاً.
    // -----------------------------------------------------

    float error =
      leftDistance - rightDistance;


    int correction =
      (int)(Kp * error);


    int leftSpeed =
      baseSpeed - correction;

    int rightSpeed =
      baseSpeed + correction;


    leftSpeed =
      constrain(
        leftSpeed,
        0,
        MAX_PWM
      );


    rightSpeed =
      constrain(
        rightSpeed,
        0,
        MAX_PWM
      );


    setMotor(
      leftSpeed,
      rightSpeed
    );


    delay(2);
  }


  stopMotors();

  delay(50);


  // -------------------------------------------------------
  // تحديث موقع الروبوت.
  // -------------------------------------------------------

  switch (robot.dir)
  {
    case NORTH:
      robot.y--;
      break;

    case EAST:
      robot.x++;
      break;

    case SOUTH:
      robot.y++;
      break;

    case WEST:
      robot.x--;
      break;
  }


  // -------------------------------------------------------
  // Safety.
  // -------------------------------------------------------

  if (robot.x < 0 ||
      robot.x >= MAZE_SIZE ||
      robot.y < 0 ||
      robot.y >= MAZE_SIZE)
  {
    Serial.println(
      "ERROR: Robot left maze!"
    );

    stopMotors();

    while (true)
    {
      delay(1000);
    }
  }


  return true;
}


// =========================================================
// 47. MOVE TO DIRECTION
// =========================================================
//
// turnTo()
// ثم moveOneCell()
// =========================================================

bool moveToDirection(
  Direction target,
  int speed
)
{
  turnTo(target);


  // بعد الدوران نفحص الـ Front مرة أخرى.

  if (!verifyFrontOpen())
  {
    return false;
  }


  return moveOneCell(speed);
}


// =========================================================
// 48. PRINT CURRENT POSITION
// =========================================================

void printRobotState()
{
  Serial.print("Position: ");

  Serial.print(robot.x);
  Serial.print(", ");
  Serial.print(robot.y);

  Serial.print(" | Direction: ");


  switch (robot.dir)
  {
    case NORTH:
      Serial.println("NORTH");
      break;

    case EAST:
      Serial.println("EAST");
      break;

    case SOUTH:
      Serial.println("SOUTH");
      break;

    case WEST:
      Serial.println("WEST");
      break;
  }
}


// =========================================================
// 49. PRINT FLOOD MAP
// =========================================================
//
// للتجارب فقط.
//
// في المنافسة يمكن تعطيل Serial.
// =========================================================

void printFloodMap()
{
  Serial.println();
  Serial.println("===== FLOOD MAP =====");


  for (int y = 0; y < MAZE_SIZE; y++)
  {
    for (int x = 0; x < MAZE_SIZE; x++)
    {
      if (flood[y][x] == 65535)
      {
        Serial.print("## ");
      }
      else
      {
        if (flood[y][x] < 10)
          Serial.print("0");

        Serial.print(flood[y][x]);
        Serial.print(" ");
      }
    }

    Serial.println();
  }


  Serial.println("=====================");
}


// =========================================================
// 50. SEARCH RUN
// =========================================================
//
// هذه هي أول مرحلة.
//
// الهدف:
// الوصول إلى الـ Center عن طريق:
//
// Sensors
//     ↓
// Map
//     ↓
// Flood Fill
//     ↓
// Direction
//     ↓
// Movement
//
// لا يوجد Wall Following.
// =========================================================

bool searchRun()
{
  Serial.println();
  Serial.println("================================");
  Serial.println("         SEARCH RUN");
  Serial.println("================================");


  while (true)
  {
    // -----------------------------------------------------
    // هل وصلنا للـ Goal؟
    // -----------------------------------------------------

    if (isGoalCell(
          robot.x,
          robot.y))
    {
      stopMotors();

      Serial.println(
        "GOAL REACHED!"
      );

      return true;
    }


    // -----------------------------------------------------
    // اقرأ الجدران الحالية.
    // -----------------------------------------------------

    senseCurrentCell();


    // -----------------------------------------------------
    // احسب Flood Fill.
    // -----------------------------------------------------

    calculateFloodFill();


    // -----------------------------------------------------
    // Debug.
    // -----------------------------------------------------

    printRobotState();


    // -----------------------------------------------------
    // اختر الاتجاه الأفضل.
    // -----------------------------------------------------

    Direction next =
      chooseNextDirection();


    Serial.print("Next direction = ");


    switch (next)
    {
      case NORTH:
        Serial.println("NORTH");
        break;

      case EAST:
        Serial.println("EAST");
        break;

      case SOUTH:
        Serial.println("SOUTH");
        break;

      case WEST:
        Serial.println("WEST");
        break;
    }


    // -----------------------------------------------------
    // تحرك خلية.
    // -----------------------------------------------------

    bool moved =
      moveToDirection(
        next,
        SEARCH_SPEED
      );


    // -----------------------------------------------------
    // إذا لم نستطع الحركة:
    //
    // غالباً Sensor اكتشف Wall لم تكن معروفة.
    //
    // نعيد Mapping + Flood Fill.
    // -----------------------------------------------------

    if (!moved)
    {
      Serial.println(
        "Path blocked - updating map."
      );

      delay(50);
    }
  }
}


// =========================================================
// 51. RETURN TO START
// =========================================================
//
// بعد الوصول للـ Goal، يمكن استخدام الـ Map للرجوع
// إلى Start.
//
// هذا ليس جزءاً من Run Time الرسمي بعد عبور Finish Line.
//
// إذا أردتم إزالة الروبوت وإعادته يدوياً، يمكن تعطيل
// هذه الوظيفة.
// =========================================================

bool returnToStart()
{
  Serial.println();
  Serial.println("Returning to START...");


  while (
    robot.x != startX ||
    robot.y != startY
  )
  {
    calculateFloodFill();


    // -----------------------------------------------------
    // هذه المرة نريد المسار من Current -> Start.
    //
    // لذلك نستخدم BFS خاص بالـ Start.
    // -----------------------------------------------------

    uint16_t distanceToStart[
      MAZE_SIZE
    ][
      MAZE_SIZE
    ];


    for (int y = 0; y < MAZE_SIZE; y++)
    {
      for (int x = 0; x < MAZE_SIZE; x++)
      {
        distanceToStart[y][x] =
          65535;
      }
    }


    int queueX[MAZE_SIZE * MAZE_SIZE];
    int queueY[MAZE_SIZE * MAZE_SIZE];

    int head = 0;
    int tail = 0;


    distanceToStart[startY][startX] = 0;

    queueX[tail] = startX;
    queueY[tail] = startY;
    tail++;


    while (head < tail)
    {
      int x = queueX[head];
      int y = queueY[head];

      head++;


      for (int d = 0; d < 4; d++)
      {
        Direction dir =
          (Direction)d;


        int nx;
        int ny;


        if (!getNeighbor(
              x,
              y,
              dir,
              nx,
              ny))
        {
          continue;
        }


        uint8_t bit =
          directionToWallBit(dir);


        if ((knownWalls[y][x] & bit) &&
            (walls[y][x] & bit))
        {
          continue;
        }


        if (
          distanceToStart[ny][nx] ==
          65535
        )
        {
          distanceToStart[ny][nx] =
            distanceToStart[y][x] + 1;


          queueX[tail] = nx;
          queueY[tail] = ny;

          tail++;
        }
      }
    }


    // -----------------------------------------------------
    // ابحث عن أفضل Neighbor من Current إلى Start.
    // -----------------------------------------------------

    Direction best =
      robot.dir;

    uint16_t bestDistance =
      65535;


    for (int d = 0; d < 4; d++)
    {
      Direction dir =
        (Direction)d;


      if (isKnownWall(dir))
      {
        continue;
      }


      int nx;
      int ny;


      if (!getNeighbor(
            robot.x,
            robot.y,
            dir,
            nx,
            ny))
      {
        continue;
      }


      if (
        distanceToStart[ny][nx]
        < bestDistance
      )
      {
        bestDistance =
          distanceToStart[ny][nx];

        best = dir;
      }
    }


    if (bestDistance == 65535)
    {
      Serial.println(
        "ERROR: Cannot return to start!"
      );

      return false;
    }


    if (!moveToDirection(
          best,
          SEARCH_SPEED
        ))
    {
      Serial.println(
        "Return path blocked."
      );
    }
  }


  stopMotors();

  Serial.println(
    "Returned to START."
  );


  return true;
}


// =========================================================
// 52. BUILD SHORTEST PATH FOR SPEED RUN
// =========================================================
//
// الآن الـ Map الذي جمعناه يحتوي على المعلومات
// التي تم اكتشافها.
//
// نحسب Flood Fill من Goal.
//
// ثم من Start نتبع القيم الأقل:
//
// 20 -> 19 -> 18 -> ... -> 0
//
// وهذا يعطينا أقصر traversable path
// بالنسبة للـ Map المعروف.
// =========================================================

bool speedRun()
{
  Serial.println();
  Serial.println("================================");
  Serial.println("          SPEED RUN");
  Serial.println("================================");


  // -------------------------------------------------------
  // يجب أن نبدأ من Start.
  // -------------------------------------------------------

  if (
    robot.x != startX ||
    robot.y != startY
  )
  {
    Serial.println(
      "ERROR: Speed Run must start at Start Cell."
    );

    return false;
  }


  // -------------------------------------------------------
  // احسب Flood Fill النهائي.
  // -------------------------------------------------------

  calculateFloodFill();


  // -------------------------------------------------------
  // تنفيذ أقصر مسار.
  // -------------------------------------------------------

  while (true)
  {
    // -----------------------------------------------------
    // Goal?
    // -----------------------------------------------------

    if (isGoalCell(
          robot.x,
          robot.y))
    {
      stopMotors();

      Serial.println(
        "SPEED RUN GOAL!"
      );

      return true;
    }


    // -----------------------------------------------------
    // اختر أقل Flood Neighbor.
    // -----------------------------------------------------

    Direction best =
      robot.dir;

    uint16_t bestValue =
      65535;


    for (int d = 0; d < 4; d++)
    {
      Direction dir =
        (Direction)d;


      // في Speed Run لا نريد Unknown walls.

      uint8_t bit =
        directionToWallBit(dir);


      if (!(knownWalls[robot.y][robot.x] & bit))
      {
        continue;
      }


      if (walls[robot.y][robot.x] & bit)
      {
        continue;
      }


      uint16_t value =
        getNeighborFlood(dir);


      if (value < bestValue)
      {
        bestValue = value;

        best = dir;
      }
    }


    // -----------------------------------------------------
    // إذا لم نجد طريق.
    // -----------------------------------------------------

    if (bestValue == 65535)
    {
      Serial.println(
        "ERROR: No known path for Speed Run."
      );

      stopMotors();

      return false;
    }


    // -----------------------------------------------------
    // تحرك بسرعة Speed Run.
    // -----------------------------------------------------

    bool moved =
      moveToDirection(
        best,
        SPEED_RUN_SPEED
      );


    if (!moved)
    {
      Serial.println(
        "Unexpected wall during Speed Run."
      );

      stopMotors();

      return false;
    }
  }
}


// =========================================================
// 53. COMPETITION MODE
// =========================================================
//
// عندما نكون في المنافسة:
//
// COMPETITION_MODE = true
//
// نوقف Debug Serial قدر الإمكان.
//
// ولا يوجد Serial command يستطيع تغيير Map.
//
// هذا يتماشى مع قاعدة أن معلومات Maze لا يتم
// إدخالها إلى الروبوت بعد كشف المتاهة.
// =========================================================

#define COMPETITION_MODE false


// =========================================================
// 54. SETUP
// =========================================================

void setup()
{
  Serial.begin(115200);

  delay(500);


  // -------------------------------------------------------
  // I2C BUS 0
  // -------------------------------------------------------

  I2C_LEFT.begin(
    I2C0_SDA,
    I2C0_SCL,
    400000
  );


  // -------------------------------------------------------
  // I2C BUS 1
  // -------------------------------------------------------

  I2C_RIGHT.begin(
    I2C1_SDA,
    I2C1_SCL,
    400000
  );


  // -------------------------------------------------------
  // Motors
  // -------------------------------------------------------

  setupMotors();


  // -------------------------------------------------------
  // Initialize Maze Map.
  // -------------------------------------------------------

  initializeMaze();


  // -------------------------------------------------------
  // Initialize AS5600.
  // -------------------------------------------------------

  resetEncoders();


  // -------------------------------------------------------
  // Initialize TOF.
  // -------------------------------------------------------

  if (!setupTOF())
  {
    Serial.println(
      "TOF INITIALIZATION FAILED!"
    );


    stopMotors();


    // توقف آمن.

    while (true)
    {
      delay(1000);
    }
  }


  // -------------------------------------------------------
  // Initial Robot Position.
  // -------------------------------------------------------

  robot.x = startX;
  robot.y = startY;

  robot.dir = NORTH;


  // -------------------------------------------------------
  // Final message.
  // -------------------------------------------------------

  Serial.println();
  Serial.println(
    "================================"
  );

  Serial.println(
    "MMRC26 MICROMOUSE READY"
  );

  Serial.println(
    "10x10 Maze"
  );

  Serial.println(
    "Cell = 180mm"
  );

  Serial.println(
    "Algorithm = Flood Fill"
  );

  Serial.println(
    "Mode = SEARCH"
  );

  Serial.println(
    "================================"
  );


  delay(1000);
}


// =========================================================
// 55. MAIN LOOP
// =========================================================
//
// في أول تشغيل:
//
// SEARCH RUN
//
// وبعد الوصول للـ Goal:
//
// الروبوت يتوقف.
//
// السبب:
// في المسابقة كل Run يبدأ من Start.
// بعد نجاح Search Run يمكن إزالة الروبوت وإعادته
// للـ Start ثم تشغيل Speed Run.
//
// هذا أفضل من جعل الروبوت يتحرك تلقائياً بعد الـ Goal
// ويصعّب عملية الـ Run management.
// =========================================================

void loop()
{
  static bool searchFinished = false;


  // -------------------------------------------------------
  // SEARCH RUN
  // -------------------------------------------------------

  if (!searchFinished)
  {
    bool success =
      searchRun();


    if (success)
    {
      searchFinished = true;


      stopMotors();


      Serial.println();
      Serial.println(
        "SEARCH COMPLETE."
      );

      Serial.println(
        "Robot reached the center."
      );

      Serial.println(
        "Map has been built."
      );


      printFloodMap();


      // ---------------------------------------------------
      // مهم:
      //
      // هنا الروبوت يتوقف.
      //
      // يتم إرجاعه إلى Start حسب طريقة إدارة الـ Run
      // التي ستستخدمونها.
      //
      // يمكنكم بعد ذلك تشغيل Speed Run.
      // ---------------------------------------------------
    }
  }


  delay(1000);
}