# camera_pub.py (예시)

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import subprocess
from pathlib import Path
from std_msgs.msg import Int32
from time import sleep

class ReceiverNode(Node):
    global status
    def __init__(self):
        super().__init__('SpeakerToCameraNode_r')
        self.subscription = self.create_subscription(
            Int32,
            'speakertocamera_topic',   # 토픽 이름 (노트북과 일치해야 함)
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        global status
        if msg.data == 1:
            status = 0
        # 카메라 보내기

class UsbCamPublisher(Node):
    def __init__(self):
        super().__init__('usb_cam_publisher')

        self.publisher_ = self.create_publisher(
            CompressedImage,
            'usb_cam/image/compressed',
            10)

        self.tmp_path = Path('/tmp/usb_cam.jpg')
        self.timer = self.create_timer(0.1, self.timer_callback)  # 0.1초마다 실행

        self.cameras = ["/dev/video0", "/dev/video1"]
        self.current_cam_idx = 0  # 현재 카메라 인덱스



    def timer_callback(self):
        current_cam = self.cameras[self.current_cam_idx]

        # fswebcam으로 캡처
        cmd = [
            'fswebcam',
            '-q',              # 조용히
            '--no-banner',     # 배너 제거
            '-S', '5',         # 앞 5프레임 버리고 6번째 저장 (검은 프레임 회피)
            '--jpeg', '90',
            '-r', '640x480',
            '--device', current_cam,
            str(self.tmp_path)
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True
            )

            # 디버깅용: fswebcam stderr 일부만 로그
            if result.stderr:
                msg = result.stderr.decode(errors='ignore')
                self.get_logger().debug(f'fswebcam stderr: {msg[:120]}')

            # 캡처된 파일이 실제로 존재하는지 확인
            if not self.tmp_path.exists():
                self.get_logger().error('Captured file does not exist')
                self._switch_camera()
                return

            size = self.tmp_path.stat().st_size
            # 너무 작은 JPEG(거의 검은 화면일 확률 높음)는 스킵
            if size < 5000:
                self.get_logger().warn(
                    f'Skipping frame (file too small: {size} bytes)'
                )
                return

            data = self.tmp_path.read_bytes()

        except Exception as e:
            self.get_logger().error(f'Failed to capture image: {e}')
            self._switch_camera()
            return

        # ROS2 메시지로 퍼블리시
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = 'jpeg'
        msg.data = data
        self.publisher_.publish(msg)
        self.get_logger().info(
            f'Published frame from {current_cam} ({len(data)} bytes)'
        )

'''
def main():
    global status
    rclpy.init()
    node1 = UsbCamPublisher()
    node2 = ReceiverNode()
    try:
         rclpy.spin_once(node)
    except KeyboardInterrupt:
         node.get_logger().info('KeyboardInterrupt, shutting down...')
    finally:
         node1.destroy_node()
         node2.destroy_node()
         rclpy.shutdown()


if __name__ == '__main__':
    main()

'''


def main():
    global status
    rclpy.init()
    node1 = UsbCamPublisher()
    node2 = ReceiverNode()
    try:
        status = 0  # Node2에서 status 업데이트한다고 가정
        node2.get_logger().info('Node2 시작') 
        # Node2 루프
        while rclpy.ok() and status != 0:
            rclpy.spin_once(node2, timeout_sec=0.1)
            # Node2에서 status 값
            # 예: status = node2.get_status()
            sleep(0.01)
        node2.get_logger().info('status가 0, Node1으로 전환')

        # Node1 루프
        print("start")
        rclpy.spin(node1)
        print("fin")

    except KeyboardInterrupt:
        node1.get_logger().info('KeyboardInterrupt, shutting down...')
        node2.get_logger().info('KeyboardInterrupt, shutting down...')
    finally:
        node1.destroy_node()
        node2.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
