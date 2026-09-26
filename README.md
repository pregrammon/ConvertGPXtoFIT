# GPX to FIT Converter (GPX转FIT转换器)

一个专业的GPS轨迹文件转换工具，支持将GPX格式文件转换为Garmin设备可用的FIT格式。
本版本为 **tkinter 桌面版**

## 功能特点

- 🚀 批量转换：一次选择多个GPX文件
- 🏃 瞬时速度：自动计算每个轨迹点的速度（FIT标准单位 m/s，3点平滑去毛刺）
- 📍 准确里程：基于 geodesic 逐段累加全程距离
- 💻 桌面GUI：tkinter 原生界面，无需浏览器

## 技术栈

- Python 3 + tkinter（标准库）
- gpxpy：解析GPX文件
- fit-tool：生成FIT文件
- geopy：地理坐标距离计算

## 安装依赖

```bash
pip install -r requirements.txt
```

> tkinter 为 Python 标准库，通常已随 Python 自带；如缺失请按平台安装（Windows 一般自带）。

## 运行

```bash
cd src
python main.py
```

## 使用说明

1. 点击「添加 GPX 文件...」选择（可多选）一个或多个 `.gpx` 文件；
2. 列表中的条目可双击或选中后点「移除选中」删除；
3. 「输出目录」留空则生成在与源文件相同的位置，也可点「浏览...」指定；
4. 点击「开始转换」，完成后弹出结果提示；
5. 同名文件自动追加 `-1`、`-2` 等序号，不会覆盖已有文件。

生成的 `.fit` 文件可直接导入 Garmin 设备。

## 项目结构

```
gpx2fit/
├── src/
│   ├── converter.py   # 核心转换逻辑（GPX -> FIT，无界面依赖）
│   └── main.py        # tkinter 桌面 GUI 入口
├── requirements.txt   # Python 依赖
└── README.md
```

## 说明

- FIT 标准中 record 的 `speed` 字段单位为 **m/s**，Garmin 设备显示时按 km/h 换算，速度正确。
- 所有转换在本地完成，文件不会上传。
