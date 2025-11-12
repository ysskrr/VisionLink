"""
Blind-Safe Camera with YOLOv8
- 웹캠 입력
- 화면을 3x3 격자로 나눔(왼쪽 위=1, 오른쪽 아래=9)
- 셀8(하단 중앙)에 '차량'이 1초 이상 '정지'하면 GO
- 화면에 차량이 전혀 1초 이상 없으면 GO
- 그 외에는 STOP
- 정지판정: 최근 1초 구간의 '하단 중앙(bottom-center) 픽셀 좌표' 최대 이동거리 <= 임계값
"""

import time
from collections import defaultdict, deque

import cv2
import numpy as np
from ultralytics import YOLO


# ==========================
# 설정값 (필요 시 조정)
# ==========================
SOURCE = 0                         # 0: 기본 웹캠
MODEL_PATH = "yolov8n.pt"          # 초경량 모델. 첫 실행 시 자동 다운로드
FONT = cv2.FONT_HERSHEY_SIMPLEX

# 관심 클래스(차량 계열)만 필터링
DETECT_CLASSES = {
    "car", "truck", "bus", "motorcycle", "motorbike", "van"
    # 필요 시 "bicycle" 추가
}

# 상태 전환 기준(초)
STATIONARY_SECONDS = 1.0           # 셀8에서 '정지'가 유지되어야 하는 시간
NO_CAR_GO_SECONDS = 1.0            # 화면에 차량이 전혀 감지되지 않는 시간

# 정지판정에 필요한 히스토리 길이(초)
HISTORY_SECONDS = 1.5              # 1초 판정 + 여유

# 셀8 경계 히스테리시스(초): 경계에서 깜빡임으로 타이머 깨지는 것 방지
INSIDE8_GRACE = 0.25

# 트래커 안정화: BoT-SORT 사용 권장 (없으면 ByteTrack)
USE_BOTSORT = True

# 디버그 오버레이
SHOW_DEBUG = True
DRAW_GRID = True


# ==========================
# 보조 함수
# ==========================
def cell_index(cx: float, cy: float, W: int, H: int) -> int:
    """3x3 그리드 셀 번호(1~9): 좌상단=1, 우하단=9"""
    col = int(np.clip(cx / (W / 3), 0, 2))  # 0,1,2
    row = int(np.clip(cy / (H / 3), 0, 2))  # 0,1,2
    return row * 3 + col + 1


def draw_grid(frame):
    H, W = frame.shape[:2]
    # 세로선
    cv2.line(frame, (W // 3, 0), (W // 3, H), (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(frame, (2 * W // 3, 0), (2 * W // 3, H), (255, 255, 255), 1, cv2.LINE_AA)
    # 가로선
    cv2.line(frame, (0, H // 3), (W, H // 3), (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(frame, (0, 2 * H // 3), (W, 2 * H // 3), (255, 255, 255), 1, cv2.LINE_AA)


def put_banner(frame, text, color=(0, 0, 255)):
    """오른쪽 위에 큼지막하게 STOP/GO 표시"""
    H, W = frame.shape[:2]
    pad = 10
    scale = 1.1
    thickness = 2
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thickness)
    x1 = W - tw - 2 * pad
    y1 = pad
    x2 = W - pad
    y2 = pad + th + 2 * pad
    cv2.rectangle(frame, (x1 - 6, y1 - 6), (x2 + 6, y2 + 6), color, -1)
    cv2.putText(frame, text, (x1, y2 - pad), FONT, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def pseudo_id_from_box(x1, y1, x2, y2, cell) -> int:
    """트랙 ID가 없을 때를 위한 임시 ID(간단 해시)"""
    return int(cell * 1e6 + round(x1 / 8) * 1000 + round(y1 / 8) * 10 + round(x2 / 8)) % 10_000_000


# ==========================
# 메인
# ==========================
def main():
    # 모델 로드
    model = YOLO(MODEL_PATH)

    # 웹캠 확인
    cap = cv2.VideoCapture(SOURCE)
    if not cap.isOpened():
        print("❌ 웹캠을 열 수 없습니다. SOURCE 인덱스를 확인하세요.")
        return
    cap.release()  # ultralytics track가 자체로 source를 연다

    # 상태 저장 구조
    # 각 track_id -> 최근 (t, (cx,cy), cell) 기록
    pos_hist = defaultdict(lambda: deque())
    # track_id가 셀8에서 '정지'로 인정되기 시작한 시각
    stationary_cell8_since = dict()

    last_any_vehicle_t = None  # 마지막 차량 감지 시각
    go_state = "STOP"

    # 추적기 실행
    tracker_name = "botsort.yaml" if USE_BOTSORT else "bytetrack.yaml"
    results_stream = model.track(
        source=SOURCE,
        stream=True,
        persist=True,
        tracker=tracker_name,
        verbose=False,
        conf=0.25  # 신뢰도 임계
    )

    for result in results_stream:
        frame = result.orig_img  # BGR
        H, W = frame.shape[:2]
        now = time.time()

        if DRAW_GRID:
            draw_grid(frame)

        boxes = result.boxes
        names = result.names  # class id -> name
        detected_any_vehicle = False

        # ========== 박스 처리 ==========
        if boxes is not None and len(boxes) > 0:
            for i in range(len(boxes)):
                # 클래스 필터
                cls_id = int(boxes.cls[i].item())
                cls_name = names.get(cls_id, str(cls_id)).lower()
                if cls_name not in DETECT_CLASSES:
                    continue

                # bbox
                xyxy = boxes.xyxy[i].tolist()  # [x1,y1,x2,y2]
                x1, y1, x2, y2 = map(int, xyxy)

                # 정지/속도 좌표: 하단 중앙(원근/흔들림에 상대적으로 강함)
                cx = (x1 + x2) / 2.0
                cy = y2
                cidx = cell_index(cx, cy, W, H)

                # 트랙 ID (없으면 임시 ID)
                tid = None
                if boxes.id is not None and boxes.id[i] is not None:
                    val = boxes.id[i].item()
                    if isinstance(val, (int, float)):
                        tid = int(val)
                if tid is None:
                    tid = pseudo_id_from_box(x1, y1, x2, y2, cidx)

                # 시각화
                color = (0, 255, 255) if cidx == 8 else (0, 200, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
                cv2.putText(frame, f"{cls_name} id:{tid} c{cidx}",
                            (x1, max(20, y1 - 6)), FONT, 0.5, color, 1, cv2.LINE_AA)

                detected_any_vehicle = True

                # 히스토리 갱신 (최근 HISTORY_SECONDS만 유지)
                hist = pos_hist[tid]
                hist.append((now, (cx, cy), cidx))
                while hist and (now - hist[0][0] > HISTORY_SECONDS):
                    hist.popleft()

                # 최근 1초 구간 윈도우
                win = [p for p in hist if now - p[0] <= 1.0]

                # 정지 판정: '최근 1초 구간'의 최대 이동거리 <= 임계값
                is_stationary = False
                max_disp = 0.0
                stationary_px = 0.0
                if len(win) >= 2:
                    coords = [(px, py) for _, (px, py), _ in win]
                    # 일부 샘플링(연산량 절약)
                    step = max(1, len(coords) // 6)
                    for (ax, ay) in coords[::step]:
                        for (bx, by) in coords:
                            d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                            if d > max_disp:
                                max_disp = d
                    # 해상도 비례 임계값(하단중심 기준, 약간 여유)
                    stationary_px = max(10.0, min(W, H) * 0.02)
                    is_stationary = (max_disp <= stationary_px)

                # 최근 1초 동안 셀8 '체류 시간' 근사 + 관용(INSIDE8_GRACE)
                inside8_time = 0.0
                if len(win) >= 2:
                    prev_t, _, prev_c = win[0]
                    for (t, _, c) in win[1:]:
                        dt = t - prev_t
                        if c == 8 or prev_c == 8:
                            inside8_time += dt
                        prev_t, prev_c = t, c

                # 셀8 정지 타이머 업데이트 (체류 + 정지 동시 만족 시)
                if (inside8_time + INSIDE8_GRACE >= STATIONARY_SECONDS) and is_stationary:
                    # 1초 채운 걸로 간주해 시작시점 보정 → 바로 GO 후보 가능
                    stationary_cell8_since.setdefault(tid, now - STATIONARY_SECONDS)
                else:
                    # 셀8 체류가 거의 없으면만 끊기게 (히스테리시스)
                    if tid in stationary_cell8_since and inside8_time < 0.1:
                        stationary_cell8_since.pop(tid, None)

                # 디버그 표시(개별)
                if SHOW_DEBUG:
                    dbg1 = f"id:{tid} c8_time:{inside8_time:.2f}s disp:{max_disp:.1f}px thr:{stationary_px:.1f}px st:{int(is_stationary)}"
                    cv2.putText(frame, dbg1, (x1, min(H - 10, y2 + 18)),
                                FONT, 0.45, (80, 220, 80), 1, cv2.LINE_AA)

        # ========== GO/STOP 결정 ==========
        go_reason = None

        # 규칙 3: 셀8 정지 1초(최우선)
        go_by_cell8 = any(now - t0 >= STATIONARY_SECONDS for t0 in stationary_cell8_since.values())
        if go_by_cell8:
            go_reason = "cell8_stationary_1s"

        # 규칙 4: 무검지 1초(셀8 정지 없을 때만)
        if not detected_any_vehicle:
            if last_any_vehicle_t is None or (now - last_any_vehicle_t >= NO_CAR_GO_SECONDS):
                if not go_by_cell8:
                    go_reason = "no_vehicle_1s"
        else:
            last_any_vehicle_t = now

        # 배너 표시
        if go_reason in ("cell8_stationary_1s", "no_vehicle_1s"):
            go_state = "GO"
            put_banner(frame, "GO", color=(0, 180, 0))
        else:
            go_state = "STOP"
            put_banner(frame, "STOP", color=(0, 0, 220))

        # 프레임 디버그
        if SHOW_DEBUG:
            dbg_state = f"state={go_state}"
            if go_reason:
                dbg_state += f" ({go_reason})"
            cv2.putText(frame, dbg_state, (10, 25), FONT, 0.6, (50, 230, 50), 2, cv2.LINE_AA)
            # 셀8 정지 후보 ID (상위 3개만)
            if stationary_cell8_since:
                first3 = list(stationary_cell8_since.keys())[:3]
                cv2.putText(frame, f"cell8_ids={first3}", (10, 50), FONT, 0.55, (50, 230, 50), 2, cv2.LINE_AA)

        cv2.imshow("Blind-Safe Camera (YOLOv8)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):  # ESC 또는 q
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
