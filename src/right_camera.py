#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Int32
from pathlib import Path
import subprocess
from pygame import mixer
import os, time

def start_speaker():
    mixer.init()
    sound = mixer.Sound('start.wav')
    sound.play()
    time.sleep(2)

class RightCameraSender(Node):
    def __init__(self):
        super().__init__('right_camera_sender')

        # 오른쪽 카메라 장치 (필요하면 /dev/video0로 변경)
        self.camera_device = "/dev/video0"

        # 활성화 플래그
        self.active = False

        # signal_topic 구독 (왼쪽 결과가 STOP(0)일 때 오른쪽 시작)
        self.signal_sub = self.create_subscription(
            Int32,
            'signal_topic',
            self.signal_callback,
            10
        )

        # right_camera 이미지 퍼블리셔
        self.image_pub = self.create_publisher(
            CompressedImage,
            'right_camera',
            10
        )

        self.tmp_path = Path('/tmp/right_cam.jpg')
        self.timer = self.create_timer(0.1, self.timer_callback)

        self.get_logger().info('RightCameraSender node started')

    def signal_callback(self, msg: Int32):
        # 설계: 왼쪽 노드가 1을 보내면 오른쪽 카메라 시작
        if msg.data == 1:
            if not self.active:
                start_speaker()
                self.get_logger().info('Received 0 on signal_topic → Right camera ACTIVATED')
            self.active = True
        else:
            if self.active:
                self.get_logger().info('Received non-0 on signal_topic → Right camera DEACTIVATED')
            self.active = False

    def timer_callback(self):
        if not self.active:
            return

        cmd = [
            'fswebcam',
            '-q',
            '--no-banner',
            '-S', '5',
            '--jpeg', '90',
            '-r', '640x480',
            '--device', self.camera_device,
            str(self.tmp_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True
            )

            if not self.tmp_path.exists():
                self.get_logger().error('Captured file does not exist')
                return

            size = self.tmp_path.stat().st_size
            if size < 5000:
                self.get_logger().warn(f'Skipping frame (file too small: {size} bytes)')
                return

            data = self.tmp_path.read_bytes()

        except Exception as e:
            self.get_logger().error(f'Failed to capture image from {self.camera_device}: {e}')
            return

        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = 'jpeg'
        msg.data = data

        self.image_pub.publish(msg)
        self.get_logger().info(f'Published RIGHT frame ({len(data)} bytes)')


def main(args=None):
    rclpy.init(args=args)
    node = RightCameraSender()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down RightCameraSender...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
