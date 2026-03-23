from gpiozero import Button
from pygame import mixer
import time

BUTTON_PIN = 17
button = Button(BUTTON_PIN)

# ======================
#   사운드 함수 5개
# ======================
def info_speaker():
    mixer.init()
    sound = mixer.Sound('start_info.wav')
    sound.play()
    time.sleep(9)

def start_speaker():
    mixer.init()
    sound = mixer.Sound('start.wav')
    sound.play()
    time.sleep(2)

def car_reco_wait_speaker():
    mixer.init()
    sound = mixer.Sound('car_reco_wait.wav')
    sound.play()
    time.sleep(6)

def stop_speaker():
    mixer.init()
    sound = mixer.Sound('stop.wav')
    sound.play()
    time.sleep(2)

def fin_speaker():
    mixer.init()
    sound = mixer.Sound('fin.wav')
    sound.play()
    time.sleep(2)


# info 이후 순서대로 실행할 사운드들
sound_sequence = [
    car_reco_wait_speaker,
    start_speaker,
    stop_speaker,
    fin_speaker
]


# ======================
#        메인
# ======================
def main():
    print("▶ info_speaker()를 반복 재생합니다. 버튼을 누르면 다음 단계로 이동합니다.")

    # ------- 1단계: info_speaker 반복 -------
    while True:
        info_speaker()
        if button.is_pressed:   # 버튼 누르는 순간 즉시 탈출
            print("🔘 버튼 눌림! info_speaker 반복 종료")
            time.sleep(0.3)
            break

    # ------- 2단계: start_speaker 즉시 실행 -------
    current_index = 0
    print("▶ start_speaker() 실행")
    sound_sequence[current_index]()
    current_index += 1

    # ------- 3단계: 버튼 누를 때마다 다음 사운드 실행 -------
    while current_index < len(sound_sequence):
        print("다음 사운드를 실행하려면 버튼을 누르세요.")

        # 버튼 눌릴 때까지 대기
        button.wait_for_press()
        print("🔘 버튼 눌림!")

        sound_sequence[current_index]()
        current_index += 1
        time.sleep(0.3)

    print("🎉 모든 사운드 실행 완료!")


if __name__ == "__main__":
    main()
