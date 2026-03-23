#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Int32
from pathlib import Path
import subprocess


class LeftCameraSender(Node):
    def __init__(self):
        super().__init__('left_camera_sender')

        # 왼쪽 카메라 장치 (필요하면 /dev/video1로 바꿔)
        self.camera_device = "/dev/video2"

        # 활성화 플래그
        self.active = False

        # speakertocamera_topic 구독 (왼쪽 카메라 시작 신호)
        self.trigger_sub = self.create_subscription(
            Int32,
            'speakertocamera_topic',
            self.trigger_callback,
            10
        )

        # (선택) signal_topic도 보고 싶으면 여기에 추가로 구독해도 됨
        # 예: 왼쪽 카메라를 GO/STOP 결과에 따라 끄고 싶다면

        # left_camera 이미지 퍼블리셔
        self.image_pub = self.create_publisher(
            CompressedImage,
            'left_camera',
            10
        )

        # 임시 파일 경로
        self.tmp_path = Path('/tmp/left_cam.jpg')

        # 0.1초마다 캡처 시도
        self.timer = self.create_timer(0.1, self.timer_callback)

        self.get_logger().info('LeftCameraSender node started')

    def trigger_callback(self, msg: Int32):
        # 예: data == 1 일 때만 왼쪽 카메라 ON
        if msg.data == 1:
            self.active = True
            self.get_logger().info('Received 1 on speakertocamera_topic → Left camera ACTIVATED')
        else:
            # 필요에 따라 끌지 말지 선택. 일단은 0이면 끄도록.
            self.active = False
            self.get_logger().info('Received non-1 on speakertocamera_topic → Left camera DEACTIVATED')

    def timer_callback(self):
        if not self.active:
            return

        cmd = [
            'fswebcam',
            '-q',
            '--no-banner',
            '-S', '5',            # 검은 프레임 몇 개 버리기
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
        self.get_logger().info(f'Published LEFT frame ({len(data)} bytes)')

def main(args=None):
    rclpy.init(args=args)
    node = LeftCameraSender()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down LeftCameraSender...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
