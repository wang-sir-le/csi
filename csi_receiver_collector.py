#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSI接收端数据采集脚本
用于从ESP32-S3接收端接收CSI数据并保存为深度学习格式

功能：
1. 连接串口读取CSI数据（ESP32-S3格式）
2. 实时解析和验证数据
3. 保存原始数据到CSV文件
4. 导出复数CSI数据为NPY文件
5. 导出幅度和相位为NPY文件

使用方法：
python csi_receiver_collector.py --port COM10 --output data/csi_raw.csv --duration 60

依赖：
pip install pyserial numpy
"""

import serial
import csv
import json
import time
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
import numpy as np
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('csi_receiver_collection.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ESP32-S3 CSI数据列名（根据app_main.c输出）
CSI_COLUMNS_ESP32S3 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth',
    'smoothing', 'not_sounding', 'aggregation', 'stbc', 'fec_coding', 'sgi',
    'noise_floor', 'ampdu_cnt', 'channel', 'secondary_channel',
    'local_timestamp', 'ant', 'sig_len', 'rx_state', 'len', 'first_word',
    'data', 'amplitude', 'phase'
]

class CSIReceiverCollector:
    """CSI接收端数据采集器"""
    
    def __init__(self, port: str, baudrate: int = 921600, timeout: float = 1.0):
        """
        初始化CSI采集器
        
        Args:
            port: 串口端口（如COM10, /dev/ttyUSB0）
            baudrate: 波特率，默认921600
            timeout: 超时时间，默认1秒
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_collecting = False
        self.data_buffer = []  # 存储解析后的数据字典
        self.csi_complex_list = []  # 存储复数CSI数组
        self.amplitude_list = []  # 存储幅度数组
        self.phase_list = []  # 存储相位数组
        self.stats = {
            'total_packets': 0,
            'valid_packets': 0,
            'invalid_packets': 0,
            'start_time': None,
            'end_time': None,
            'data_rate_hz': 0
        }
        
    def connect(self) -> bool:
        """连接串口"""
        try:
            logger.info(f"正在连接串口 {self.port}，波特率 {self.baudrate}")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            if self.serial_conn.is_open:
                logger.info("串口连接成功")
                # 清空缓冲区
                self.serial_conn.reset_input_buffer()
                time.sleep(0.1)
                return True
            else:
                logger.error("串口连接失败")
                return False
                
        except serial.SerialException as e:
            logger.error(f"串口连接错误: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("串口连接已关闭")
    
    def parse_array_string(self, array_str: str, warn: bool = True) -> List[float]:
        """
        解析类似 "[1.0,2.0,3.0]" 的字符串为浮点数列表
        
        Args:
            array_str: 数组字符串
            
        Returns:
            浮点数列表，解析失败返回空列表
        """
        if not array_str:
            return []
        # 去除引号、方括号和空格
        array_str = array_str.strip()
        if array_str.startswith('"[') and array_str.endswith(']"'):
            array_str = array_str[2:-2]
        elif array_str.startswith('[') and array_str.endswith(']'):
            array_str = array_str[1:-1]
        if not array_str:
            return []
        if '%f' in array_str:
            return []
        try:
            return [float(x.strip()) for x in array_str.split(',') if x.strip()]
        except ValueError as e:
            logger.warning(f"数组解析错误 '{array_str}': {e}")
            return []

    def format_array_string(self, values: List[float]) -> str:
        """Format numeric arrays for CSV storage."""
        return '[' + ','.join(f'{value:.6g}' for value in values) + ']'

    def build_csi_from_raw_data(self, data_array: List[float]) -> Optional[Dict[str, List]]:
        """
        Build complex CSI, amplitude, and phase from interleaved raw CSI data.

        ESP CSI raw data is stored as imag, real pairs:
        real = data[2*i + 1], imag = data[2*i].
        """
        if len(data_array) < 2 or len(data_array) % 2 != 0:
            return None

        csi_complex = []
        amplitude_array = []
        phase_array = []

        for i in range(0, len(data_array), 2):
            imag = data_array[i]
            real = data_array[i + 1]
            csi_complex.append(complex(real, imag))
            amplitude_array.append(float(np.hypot(real, imag)))
            phase_array.append(float(np.arctan2(imag, real)))

        return {
            'csi_complex': csi_complex,
            'amplitude_array': amplitude_array,
            'phase_array': phase_array,
        }

    def split_csi_fields(self, line: str) -> Optional[List[str]]:
        """
        以 CSV 规则解析 CSI 行，正确处理带引号的数组字段。

        Args:
            line: 原始 CSI 字符串

        Returns:
            解析后的字段列表，失败返回 None
        """
        try:
            fields = next(csv.reader([line], delimiter=',', quotechar='"', skipinitialspace=False))
            return [field.strip() for field in fields]
        except (csv.Error, StopIteration) as e:
            logger.warning(f"CSV字段解析失败: {e}")
            return None
    
    def parse_csi_line(self, line: str) -> Optional[Dict]:
        """
        解析CSI数据行（ESP32-S3格式）
        
        Args:
            line: 原始数据行
            
        Returns:
            解析后的数据字典，如果解析失败返回None
        """
        try:
            # 去除换行符和空白字符
            line = line.replace('\x00', '').strip()
            if not line:
                return None
            
            # 检查是否为CSI数据行
            if not line.startswith("CSI_DATA"):
                return None
            
            # 按 CSV 规则分割字段，避免数组字段中的逗号被误拆
            parts = self.split_csi_fields(line)
            if not parts:
                return None

            if len(parts) != len(CSI_COLUMNS_ESP32S3):
                logger.warning(f"数据字段数量不正确: {len(parts)}，期望{len(CSI_COLUMNS_ESP32S3)}")
                return None
            
            # 解析基本字段
            parsed_data = {}
            for i, col in enumerate(CSI_COLUMNS_ESP32S3):
                if i < len(parts):
                    parsed_data[col] = parts[i].strip()
            
            # 解析CSI数据数组（原始整数）
            data_str = parsed_data.get('data', '')
            data_array = self.parse_array_string(data_str)
            parsed_data['data_array'] = data_array
            parsed_data['data_length'] = len(data_array)
            
            # 解析幅度数组
            amplitude_str = parsed_data.get('amplitude', '')
            amplitude_array = self.parse_array_string(amplitude_str)
            parsed_data['amplitude_array'] = amplitude_array
            
            # 解析相位数组
            phase_str = parsed_data.get('phase', '')
            phase_array = self.parse_array_string(phase_str)
            parsed_data['phase_array'] = phase_array

            raw_csi = self.build_csi_from_raw_data(data_array)
            if raw_csi:
                amplitude_array = raw_csi['amplitude_array']
                phase_array = raw_csi['phase_array']
                parsed_data['amplitude_array'] = amplitude_array
                parsed_data['phase_array'] = phase_array
                parsed_data['amplitude'] = self.format_array_string(amplitude_array)
                parsed_data['phase'] = self.format_array_string(phase_array)
            
            # 计算复数形式的CSI数据（原始数据中实部和虚部交错）
            # 根据app_main.c，原始数据格式为: buf[0] = 虚部？需要确认
            # 但幅度和相位已经计算，我们可以直接使用幅度和相位重构复数
            if len(amplitude_array) == len(phase_array) and len(amplitude_array) > 0:
                csi_complex = []
                for amp, ph in zip(amplitude_array, phase_array):
                    real = amp * np.cos(ph)
                    imag = amp * np.sin(ph)
                    csi_complex.append(complex(real, imag))
                parsed_data['csi_complex'] = csi_complex
                parsed_data['subcarrier_count'] = len(csi_complex)
            else:
                # 如果幅度/相位解析失败，尝试从原始数据数组重构
                # 假设原始数据为交错存储的实部和虚部：buf[0] = 虚部？实际上代码中 real = buf[2*i+1], imag = buf[2*i]
                # 因此 data_array 中偶数索引为虚部，奇数索引为实部
                if len(data_array) % 2 == 0:
                    csi_complex = []
                    for i in range(0, len(data_array), 2):
                        imag = data_array[i]   # 根据代码，buf[2*i] 是虚部
                        real = data_array[i+1] # buf[2*i+1] 是实部
                        csi_complex.append(complex(real, imag))
                    parsed_data['csi_complex'] = csi_complex
                    parsed_data['subcarrier_count'] = len(csi_complex)
            
            # 添加时间戳
            if raw_csi:
                parsed_data['csi_complex'] = raw_csi['csi_complex']
                parsed_data['subcarrier_count'] = len(raw_csi['csi_complex'])

            parsed_data['collection_timestamp'] = time.time()
            parsed_data['collection_datetime'] = datetime.now().isoformat()
            
            return parsed_data
            
        except Exception as e:
            logger.error(f"数据解析异常: {e}")
            return None
    
    def validate_csi_data(self, data: Dict) -> bool:
        """
        验证CSI数据质量
        
        Args:
            data: 解析后的CSI数据
            
        Returns:
            数据是否有效
        """
        try:
            # 检查必要字段
            required_fields = ['type', 'mac', 'rssi', 'data_array']
            for field in required_fields:
                if field not in data:
                    logger.warning(f"缺少必要字段: {field}")
                    return False
            
            # 检查RSSI信号强度
            try:
                rssi = float(data['rssi'])
                if rssi > 0 or rssi < -110:
                    logger.warning(f"RSSI值异常: {rssi} dBm")
                    return False
                if rssi > -20:
                    logger.debug(f"RSSI信号较强: {rssi} dBm")
            except ValueError:
                logger.warning("RSSI值格式错误")
                return False
            
            # 检查CSI数据长度
            if 'data_length' in data:
                data_len = data['data_length']
                if data_len < 64 or data_len > 512:  # 合理的CSI数据长度范围
                    logger.warning(f"CSI数据长度异常: {data_len}")
                    return False
            
            # 检查子载波数量
            if 'subcarrier_count' in data:
                subcarrier_count = data['subcarrier_count']
                if subcarrier_count < 32:
                    logger.warning(f"子载波数量不足: {subcarrier_count}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"数据验证异常: {e}")
            return False
    
    def collect_data(self, duration_seconds: int, output_csv: str, output_npy_prefix: Optional[str] = None):
        """
        采集CSI数据
        
        Args:
            duration_seconds: 采集时长（秒）
            output_csv: 输出CSV文件路径
            output_npy_prefix: 输出NPY文件前缀（可选）
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("串口未连接，请先调用connect()方法")
            return
        
        logger.info(f"开始采集数据，时长: {duration_seconds}秒，输出CSV: {output_csv}")
        
        # 准备输出目录
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化统计信息
        self.stats = {
            'total_packets': 0,
            'valid_packets': 0,
            'invalid_packets': 0,
            'start_time': time.time(),
            'end_time': None,
            'data_rate_hz': 0
        }
        
        self.is_collecting = True
        self.data_buffer = []
        self.csi_complex_list = []
        self.amplitude_list = []
        self.phase_list = []
        
        start_time = time.time()
        last_print_time = start_time
        
        try:
            with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
                # 创建CSV写入器
                fieldnames = CSI_COLUMNS_ESP32S3 + [
                    'collection_timestamp', 
                    'collection_datetime',
                    'data_length',
                    'subcarrier_count',
                    'is_valid'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # 数据采集循环
                while self.is_collecting and (time.time() - start_time) < duration_seconds:
                    try:
                        # 读取一行数据
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        self.stats['total_packets'] += 1
                        
                        # 解析数据
                        parsed_data = self.parse_csi_line(line)
                        
                        if parsed_data:
                            # 验证数据质量
                            is_valid = self.validate_csi_data(parsed_data)
                            parsed_data['is_valid'] = is_valid
                            
                            if is_valid:
                                self.stats['valid_packets'] += 1
                                self.data_buffer.append(parsed_data)
                                
                                # 存储复数CSI、幅度和相位
                                if parsed_data.get('csi_complex'):
                                    self.csi_complex_list.append(parsed_data['csi_complex'])
                                if parsed_data.get('amplitude_array'):
                                    self.amplitude_list.append(parsed_data['amplitude_array'])
                                if parsed_data.get('phase_array'):
                                    self.phase_list.append(parsed_data['phase_array'])
                                
                                # 写入CSV文件（只写入基本字段，不包含数组数据）
                                row_data = {}
                                for col in CSI_COLUMNS_ESP32S3:
                                    row_data[col] = parsed_data.get(col, '')
                                
                                row_data['collection_timestamp'] = parsed_data['collection_timestamp']
                                row_data['collection_datetime'] = parsed_data['collection_datetime']
                                row_data['data_length'] = parsed_data.get('data_length', '')
                                row_data['subcarrier_count'] = parsed_data.get('subcarrier_count', '')
                                row_data['is_valid'] = is_valid
                                
                                writer.writerow(row_data)
                            else:
                                self.stats['invalid_packets'] += 1
                        
                        # 每5秒打印一次进度
                        current_time = time.time()
                        if current_time - last_print_time >= 5:
                            elapsed = current_time - start_time
                            remaining = duration_seconds - elapsed
                            rate = self.stats['valid_packets'] / elapsed if elapsed > 0 else 0
                            logger.info(f"进度: {elapsed:.1f}s / {duration_seconds}s, "
                                      f"有效数据包: {self.stats['valid_packets']}, "
                                      f"速率: {rate:.1f} Hz")
                            last_print_time = current_time
                            
                    except Exception as e:
                        logger.error(f"数据读取异常: {e}")
                        continue
                
                # 采集结束
                self.is_collecting = False
                self.stats['end_time'] = time.time()
                total_time = self.stats['end_time'] - self.stats['start_time']
                self.stats['data_rate_hz'] = self.stats['valid_packets'] / total_time if total_time > 0 else 0
                
                logger.info(f"数据采集完成，总时长: {total_time:.1f}s，有效数据包: {self.stats['valid_packets']}，平均速率: {self.stats['data_rate_hz']:.1f} Hz")
                
                # 保存NPY文件
                if output_npy_prefix and self.csi_complex_list:
                    self.save_npy_files(output_npy_prefix)
                
                # 保存统计信息
                self.save_stats(output_csv.replace('.csv', '_stats.json'))
                
        except Exception as e:
            logger.error(f"数据采集过程异常: {e}")
            self.is_collecting = False
    
    def save_npy_files(self, prefix: str):
        """
        保存NPY文件
        
        Args:
            prefix: 文件前缀
        """
        try:
            if self.csi_complex_list:
                # 转换为numpy数组，形状为 (样本数, 子载波数)
                csi_array = np.array(self.csi_complex_list, dtype=np.complex64)
                np.save(f"{prefix}_csi_complex.npy", csi_array)
                logger.info(f"复数CSI数据已保存到 {prefix}_csi_complex.npy，形状: {csi_array.shape}")
            
            if self.amplitude_list:
                amplitude_array = np.array(self.amplitude_list, dtype=np.float32)
                np.save(f"{prefix}_amplitude.npy", amplitude_array)
                logger.info(f"幅度数据已保存到 {prefix}_amplitude.npy，形状: {amplitude_array.shape}")
            
            if self.phase_list:
                phase_array = np.array(self.phase_list, dtype=np.float32)
                np.save(f"{prefix}_phase.npy", phase_array)
                logger.info(f"相位数据已保存到 {prefix}_phase.npy，形状: {phase_array.shape}")
                
        except Exception as e:
            logger.error(f"保存NPY文件失败: {e}")
    
    def save_stats(self, stats_file: str):
        """
        保存统计信息到JSON文件
        
        Args:
            stats_file: 统计文件路径
        """
        try:
            stats = self.stats.copy()
            stats['total_time'] = stats['end_time'] - stats['start_time'] if stats['end_time'] and stats['start_time'] else 0
            stats['valid_ratio'] = stats['valid_packets'] / stats['total_packets'] if stats['total_packets'] > 0 else 0
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)
            
            logger.info(f"统计信息已保存到 {stats_file}")
        except Exception as e:
            logger.error(f"保存统计信息失败: {e}")

def main():
    parser = argparse.ArgumentParser(description='CSI接收端数据采集脚本')
    parser.add_argument('--port', type=str, required=True, help='串口端口 (例如 COM10 或 /dev/ttyUSB0)')
    parser.add_argument('--baudrate', type=int, default=921600, help='波特率，默认 921600')
    parser.add_argument('--output', type=str, default='data/csi_raw.csv', help='输出CSV文件路径，默认 data/csi_raw.csv')
    parser.add_argument('--npy_prefix', type=str, help='NPY文件前缀（可选），例如 data/csi，将生成 data/csi_csi_complex.npy 等')
    parser.add_argument('--duration', type=int, default=60, help='采集时长（秒），默认 60')
    parser.add_argument('--timeout', type=float, default=1.0, help='串口超时时间（秒），默认 1.0')
    
    args = parser.parse_args()
    
    # 创建采集器
    collector = CSIReceiverCollector(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )
    
    # 连接串口
    if not collector.connect():
        logger.error("无法连接串口，程序退出")
        sys.exit(1)
    
    try:
        # 开始采集数据
        collector.collect_data(
            duration_seconds=args.duration,
            output_csv=args.output,
            output_npy_prefix=args.npy_prefix
        )
    except KeyboardInterrupt:
        logger.info("用户中断，停止采集")
    finally:
        collector.disconnect()

if __name__ == '__main__':
    main()
