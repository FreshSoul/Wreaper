import csv

# 读取 Wwise Capture Log（假设是 "wwise_log.txt"）
input_file = "C:\\Users\\lanmeipai\\Desktop\\Capture.txt"
output_file = "reaper_markers.csv"

# 解析 TXT 并转换格式
with open(input_file, "r") as infile, open(output_file, "w", newline="") as outfile:
    writer = csv.writer(outfile)
    writer.writerow(["Position", "Name"])  # CSV 头部
    for line in infile:
        parts = line.strip().split("|")  # 按 | 分割
        if len(parts) == 2:
            time = parts[0].strip()
            event = parts[1].strip()
            writer.writerow([time, event])

print(f"✅ 转换完成！请在 Reaper 导入 {output_file}")



