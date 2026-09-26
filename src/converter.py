# -*- coding: utf-8 -*-
"""GPX 转 FIT 核心转换逻辑（无界面/无 Web 依赖，供任意 GUI 调用）。"""
from io import BytesIO
from datetime import datetime

import gpxpy
from geopy.distance import geodesic

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.profile_type import (
    FileType,
    TimerTrigger,
    Event,
    EventType,
    Sport,
    SubSport,
    SessionTrigger,
)

# 设备常量
MANUFACTURER = 1  # Garmin
GARMIN_PRODUCT = 3415  # Forerunner 245
GARMIN_SOFTWARE_VERSION = 3.58
GARMIN_SERIAL_NUMBER = 1234567890


def _resolve_start_time_ms(gpx_data):
    """解析活动开始时间（Unix毫秒）。

    很多GPX文件的 metadata.time 为空（如手机健康App导出的轨迹），
    此时回退到第一个轨迹点的时间；若完全没有时间信息，则使用当前时间。
    """
    t = getattr(gpx_data, 'time', None)
    if t is not None:
        return int(t.timestamp() * 1000)

    for track in gpx_data.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time is not None:
                    return int(point.time.timestamp() * 1000)

    return int(datetime.now().timestamp() * 1000)


def _compute_points(gpx_data, time_create):
    """按轨迹顺序收集所有轨迹点，并计算累计距离与瞬时速度。

    返回每个轨迹一个列表，列表元素为 dict:
      lat/lon/ele/ts_ms(时间戳毫秒)/dist(累计距离m)/delta(本点到前一点距离)/speed(瞬时速度m/s,3点平滑)
    距离用 geodesic 逐段累加；瞬时速度 = 相邻点距离差 / 时间差，再做3点居中平滑。
    """
    per_track = []
    prev_coordinate = None
    prev_time = None
    global_distance = 0.0

    for track in gpx_data.tracks:
        pts = []
        for segment in track.segments:
            for track_point in segment.points:
                current_time = track_point.time
                # 部分GPX轨迹点可能缺少时间，用前一点/开始时间兜底
                if current_time is None:
                    current_time = prev_time if prev_time is not None \
                        else datetime.fromtimestamp(time_create / 1000)

                ts_ms = int(current_time.timestamp() * 1000)
                current_coordinate = (track_point.latitude, track_point.longitude)

                delta = 0.0
                if prev_coordinate is not None:
                    d = geodesic(prev_coordinate, current_coordinate).meters
                    if d > 0:
                        delta = d

                global_distance += delta

                pts.append({
                    'lat': track_point.latitude,
                    'lon': track_point.longitude,
                    'ele': track_point.elevation,
                    'ts_ms': ts_ms,
                    'dist': global_distance,
                    'delta': delta,
                    'speed': None,
                })

                prev_coordinate = current_coordinate
                prev_time = current_time
        per_track.append(pts)

    # 计算相邻点瞬时速度（m/s）
    flat = [p for pts in per_track for p in pts]
    speeds = [None] * len(flat)
    for i in range(1, len(flat)):
        dd = flat[i]['dist'] - flat[i - 1]['dist']
        dt = (flat[i]['ts_ms'] - flat[i - 1]['ts_ms']) / 1000.0
        if dt > 0 and dd >= 0:
            speeds[i] = dd / dt

    # 3点居中平滑，减少GPS抖动造成的速度毛刺
    for i in range(len(flat)):
        vals = [speeds[j] for j in (i - 1, i, i + 1)
                if 0 <= j < len(flat) and speeds[j] is not None]
        if vals:
            flat[i]['speed'] = sum(vals) / len(vals)

    return per_track


def gpx_to_fit(gpx_data):
    """将GPX数据转换为FIT文件对象。速度以 FIT 标准单位 m/s 写入。"""
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    # 获取活动开始时间（metadata.time 为空时自动回退到第一个轨迹点）
    time_create = _resolve_start_time_ms(gpx_data)

    # 文件ID
    message = FileIdMessage()
    message.local_id = 0
    message.type = FileType.ACTIVITY
    message.manufacturer = MANUFACTURER
    message.product = GARMIN_PRODUCT
    message.time_created = time_create
    message.serial_number = GARMIN_SERIAL_NUMBER
    builder.add(message)

    # 设备信息
    message = DeviceInfoMessage()
    message.local_id = 1
    message.serial_number = GARMIN_SERIAL_NUMBER
    message.manufacturer = MANUFACTURER
    message.garmin_product = GARMIN_PRODUCT
    message.software_version = GARMIN_SOFTWARE_VERSION
    message.device_index = 0
    message.source_type = 5
    message.product = GARMIN_PRODUCT
    builder.add(message)

    # 开始事件
    message = EventMessage()
    message.local_id = 2
    message.event = Event.TIMER
    message.event_type = EventType.START
    message.event_group = 0
    message.timer_trigger = TimerTrigger.MANUAL
    message.timestamp = time_create
    builder.add(message)

    per_track = _compute_points(gpx_data, time_create)
    flat = [p for pts in per_track for p in pts]
    last_record_ms = flat[-1]['ts_ms'] if flat else time_create

    # 组装记录点
    records = []
    prev_track_end_dist = 0.0
    for track_index, pts in enumerate(per_track):
        if not pts:
            continue

        track_distance = pts[-1]['dist'] - prev_track_end_dist
        prev_track_end_dist = pts[-1]['dist']

        for point in pts:
            message = RecordMessage()
            message.local_id = 3
            message.position_lat = point['lat']
            message.position_long = point['lon']
            message.distance = point['dist']
            if point['ele'] is not None:
                message.altitude = point['ele']
            if point['speed'] is not None:
                message.speed = point['speed']  # 单位 m/s（FIT 标准）
            message.timestamp = point['ts_ms']
            records.append(message)

        # 本轨迹的移动时间（相邻间隔小于60秒）
        track_moving_time = 0.0
        for i in range(1, len(pts)):
            dt = (pts[i]['ts_ms'] - pts[i - 1]['ts_ms']) / 1000.0
            if 0 < dt < 60:
                track_moving_time += dt

        # Lap信息（按轨迹生成）
        message = LapMessage()
        message.local_id = 4
        message.timestamp = pts[-1]['ts_ms']
        message.message_index = track_index
        message.start_time = pts[0]['ts_ms']
        message.total_elapsed_time = track_moving_time
        message.total_timer_time = track_moving_time
        message.start_position_lat = pts[0]['lat']
        message.start_position_long = pts[0]['lon']
        message.end_position_lat = pts[-1]['lat']
        message.end_position_long = pts[-1]['lon']
        message.total_distance = track_distance
        message.sport = Sport.CYCLING
        builder.add(message)

        # Session信息
        message = SessionMessage()
        message.local_id = 5
        message.timestamp = pts[-1]['ts_ms']
        message.start_time = pts[0]['ts_ms']
        message.total_elapsed_time = track_moving_time
        message.total_timer_time = track_moving_time
        message.start_position_lat = pts[0]['lat']
        message.start_position_long = pts[0]['lon']
        message.sport = Sport.CYCLING
        message.sub_sport = SubSport.GENERIC
        message.first_lap_index = 0
        message.num_laps = 1
        message.trigger = SessionTrigger.ACTIVITY_END
        message.event = Event.SESSION
        message.event_type = EventType.STOP
        message.total_distance = track_distance
        builder.add(message)

    builder.add_all(records)

    # 结束事件
    message = EventMessage()
    message.local_id = 2
    message.event = Event.TIMER
    message.event_type = EventType.STOP
    message.event_group = 0
    message.timer_trigger = TimerTrigger.MANUAL
    message.timestamp = last_record_ms
    builder.add(message)

    return builder.build()


def load_gpx(gpx_path):
    """读取本地 GPX 文件并返回解析后的 gpxpy 对象。"""
    with open(gpx_path, 'r', encoding='utf-8') as f:
        return gpxpy.parse(f)
