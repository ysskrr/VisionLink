# 파일명: receiver_node_serial.py
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import serial
from pygame import mixer
import os, time

def stop_speaker():
    mixer.init()
    sound = mixer.Sound('stop.wav')
    sound.play()
    time.sleep(2)

class ReceiverNode(Node):
    def __init__(self):
        super().__init__('receiver_node')

        # ROS2 Subscriber
        self.subscription = self.create_subscription(
            Int32,
            'signal_topic',   # 노트북 송신 토픽 이름
            self.listener_callback,
            10
        )

        # ✅ 아두이노 연결 시리얼 포트 설정
        # (USB로 연결한 경우 일반적으로 /dev/ttyACM0 또는 /dev/ttyUSB0)
        try:
            self.serial_port = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
            time.sleep(2)  # 포트 초기화 대기
            self.get_logger().info('✅ Serial connection to Arduino opened.')
        except serial.SerialException as e:
            self.get_logger().error(f'❌ Serial connection failed: {e}')
            self.serial_port = None

    def listener_callback(self, msg):
        data_str = str(msg.data)
        self.get_logger().info(f'📩 Received: {data_str}')
        if data_str == 0:
            stop_speaker()
        # 아두이노로 전송
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write((data_str + '\n').encode('utf-8'))
                self.get_logger().info(f'➡️ Sent to Arduino: {data_str}')
            except Exception as e:
                self.get_logger().error(f'⚠️ Serial send error: {e}')
        else:
            self.get_logger().warn('⚠️ Serial not available.')

    def destroy_node(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.get_logger().info('🔌 Serial port closed.')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReceiverNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
