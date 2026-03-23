import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import RPi.GPIO as GPIO
import time
from gpiozero import Button
from pygame import mixer
import os, time

BUTTON_PIN = 17
button = Button(BUTTON_PIN)
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
    time.sleep(3)

def fin_speaker():
    mixer.init()
    sound = mixer.Sound('fin.wav')
    sound.play()
    time.sleep(3)

class SpeakerToCameraNode(Node):
    def __init__(self):
        super().__init__('SpeakerToCameraNode_s')
        self.publisher = self.create_publisher(Int32, 'speakertocamera_topic', 10)

    def publish_signal(self, value: int):
        msg = Int32()
        msg.data = value
        self.publisher.publish(msg)
        self.get_logger().info(f'📤 Sent: {value}')


def main(args=None):
    rclpy.init(args=args)
    node = SpeakerToCameraNode()
    try:
        while True:
            info_speaker() # 스피커 나오는 동안 아랫줄 코드로 안넘어가는지 확인
            if button.is_pressed:
                car_reco_wait_speaker()
                node.publish_signal(1) # 왼쪽 카메라 인식 노드 호출.
                break
            time.sleep(0.1)
        while True:
            if button.is_pressed:
                fin_speaker()
                break
    except KeyboardInterrupt:
        GPIO.cleanup()

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
