import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
from tkinter import Tk, filedialog, messagebox
from matplotlib import rcParams
from tqdm import tqdm
import warnings
import soundfile as sf
from scipy import signal
from pathlib import Path



def plot_spectrogram_2d(audio_path, output_dir, sr=22050, n_fft=2048, hop_length=512, y_axis="linear"):
    """
    绘制音频频谱图并保存

    参数:
        audio_path (str): 音频文件路径
        output_dir (str): 图片输出目录
        sr (int): 采样率
        n_fft (int): FFT窗口大小
        hop_length (int): 帧移
        y_axis (str): 频率轴类型，"linear"或"log"
    """
    try:
        # 加载音频文件
        y, sr = librosa.load(audio_path, sr=sr)

        # 获取音频文件名(不带扩展名)
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]

        # 计算短时傅里叶变换(STFT)
        D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)

        # 将幅度转换为dB
        S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)

        # 创建图形
        plt.figure(figsize=(12, 6))

        # 显示频谱图
        img = librosa.display.specshow(S_db, sr=sr, hop_length=hop_length,
                                       x_axis='time', y_axis=y_axis)

        plt.colorbar(img, format='%+2.0f dB')
        plt.title(f'音频频谱分析 - {audio_name}')
        plt.xlabel('时间 (分)')
        plt.ylabel('频率 (Hz)')

        # 构造输出路径
        output_path = os.path.join(output_dir, f"{audio_name}_频谱图.png")

        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()  # 关闭图形以释放内存

        return True, output_path
    except Exception as e:
        return False, f"处理 {audio_path} 时出错: {str(e)}"


def batch_process_audio_2d(input_dir, output_dir):
    """
    批量处理音频文件

    参数:
        input_dir (str): 输入目录路径
        output_dir (str): 输出目录路径
    """
    # 支持的音频格式
    supported_formats = ('.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac')

    # 收集所有音频文件
    audio_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(supported_formats):
                audio_files.append(os.path.join(root, file))

    if not audio_files:
        messagebox.showwarning("警告", "所选目录中没有找到支持的音频文件!")
        return

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 使用进度条处理文件
    success_count = 0
    error_messages = []

    for audio_file in tqdm(audio_files, desc="正在生成频谱图", unit="文件"):
        success, result = plot_spectrogram_2d(audio_file, output_dir)
        if success:
            success_count += 1
        else:
            error_messages.append(result)

    # 显示处理结果
    result_message = f"处理完成!\n\n成功处理: {success_count} 个文件"
    if error_messages:
        result_message += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        # 保存错误日志
        log_path = os.path.join(output_dir, "processing_errors.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(error_messages))

    messagebox.showinfo("处理结果", result_message)

    # 完成后打开输出文件夹
    if os.name == 'nt':  # Windows
        os.startfile(output_dir)
    elif os.name == 'posix':  # macOS/Linux
        os.system(f'open "{output_dir}"' if sys.platform == 'darwin' else f'xdg-open "{output_dir}"')


def select_directory_2d(title):
    """
    弹出文件夹选择对话框
    """
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    folder = filedialog.askdirectory(title=title)
    return folder if folder else None


def process_long_audio_3d(file_path, output_dir, db_range=(-120, 9), chunk_size=30):
    try:
        # 读取音频文件
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            audio_data, sample_rate = sf.read(file_path, dtype='float32')

        # 处理立体声转单声道
        mono_audio = audio_data.mean(axis=1) if audio_data.ndim > 1 else audio_data

        # 计算频谱图
        duration = len(mono_audio) / sample_rate
        nperseg = 512 if duration > 300 else 1024

        frequencies, times, Sxx = signal.spectrogram(
            mono_audio,
            fs=sample_rate,
            window='hann',
            nperseg=nperseg,
            noverlap=nperseg // 2,
            scaling='density'
        )

        # 转换为dB并限制范围
        Sxx_db = 10 * np.log10(Sxx + 1e-12)
        Sxx_db = np.clip(Sxx_db, db_range[0], db_range[1])

        # 1. 强制设置最低频率为20Hz并过滤
        min_freq = 20
        valid_mask = frequencies >= min_freq
        frequencies = frequencies[valid_mask]
        Sxx_db = Sxx_db[valid_mask, :]

        # 2. 对数变换并重置基准
        log_freq = np.log10(frequencies)
        Y_values = log_freq - np.log10(min_freq)  # 使20Hz对应Y=0

        # 3. 确保最低点正好在基底上
        Y_values = np.maximum(Y_values, 0)  # 强制非负
        Y_values[0] = 0  # 确保第一个点完全在基底上

        # 创建3D图
        fig = plt.figure(figsize=(20, 12))
        ax = fig.add_subplot(111, projection='3d')

        # 降低数据量
        t_stride = max(1, len(times) // 200)
        f_stride = 1  # 不再对频率下采样，确保基底连接

        X, Y = np.meshgrid(times[::t_stride], Y_values[::f_stride])
        Z = Sxx_db[::f_stride, ::t_stride]

        # 绘制频谱曲面（确保连接基底）
        surf = ax.plot_surface(
            X, Y, Z,
            cmap='inferno',
            rstride=1,
            cstride=1,
            linewidth=0,
            antialiased=False,
            vmin=db_range[0],
            vmax=db_range[1],
            edgecolor='none'  # 去除边缘线
        )

        # 4. 精确绘制基底平面（与曲面共享网格）
        base_z = np.full_like(Z, db_range[0])
        base_z[0, :] = Z[0, :]  # 让基底第一行与曲面重合
        ax.plot_surface(X, Y * 0, base_z, color='black', alpha=0.3, zorder=0)

        # 5. 强制设置坐标范围
        ax.set_zlim(db_range[0], db_range[1])
        ax.set_ylim(0, np.max(Y_values) * 1.05)
        # === 关键修改结束 ===

        # 设置坐标轴
        ax.set_xlabel('时间 (分钟)', fontsize=12)
        ax.set_ylabel('频率 (Hz)', fontsize=12)
        ax.set_zlabel(f'强度 (dB)\n范围:{db_range[0]}~{db_range[1]}', fontsize=12)

        # 时间轴刻度（分钟）
        ax.set_xticks(np.linspace(0, max(times), 6))
        ax.set_xticklabels([f"{x / 60:.1f}" for x in np.linspace(0, max(times), 6)])

        # 频率轴刻度（对齐新基准）
        freq_ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
        freq_ticks = [f for f in freq_ticks if min_freq <= f <= sample_rate / 2]
        ax.set_yticks(np.log10(freq_ticks) - np.log10(min_freq))
        ax.set_yticklabels([f"{f / 1000:.1f}k" if f >= 1000 else str(f) for f in freq_ticks])

        # 颜色条
        cbar = fig.colorbar(surf, ax=ax, shrink=0.6, aspect=10)
        cbar.set_label('强度 (dB)', fontsize=12)

        # 标题和保存
        filename = os.path.splitext(os.path.basename(file_path))[0]
        plt.title(f'3D频谱图 - {filename}\n时长: {duration // 60:.0f}分{duration % 60:.0f}秒', fontsize=14)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{filename}_3D频谱.png")
        plt.savefig(output_path, dpi=200, bbox_inches='tight')
        plt.close()

        print(f"成功生成: {output_path}")
        return output_path
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {str(e)}")
        plt.close()
        return None

def plot_spectrogram_3d(file_path, output_dir):
    """包装器：调用处理函数并统一返回 (success, result)。result 为输出路径或错误信息。"""
    try:
        out_path = process_long_audio_3d(file_path, output_dir)
        if out_path and os.path.isfile(out_path):
            return True, out_path
        # 兼容旧路径规则的兜底判断
        filename = os.path.splitext(os.path.basename(file_path))[0]
        expected = os.path.join(output_dir, f"{filename}_3D频谱.png")
        return (True, expected) if os.path.isfile(expected) else (False, f"生成失败（未找到输出文件）: {file_path}")
    except Exception as e:
        return False, f"{file_path}: {e}"

def batch_process_audio_3d(input_dir, output_dir):
    supported_formats = ('.wav', '.wave', '.aiff', '.flac')
    
    audio_files =[]
    for root, _,files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(supported_formats):
                audio_files.append(os.path.join(root, file))
    
    if not audio_files:
        messagebox.showwarning("警告", "未找到支持的音频文件")
        return
    
    os.makedirs(output_dir, exist_ok=True)

    # 使用进度条处理文件
    success_count = 0
    error_messages = []

    for audio_file in tqdm(audio_files, desc="正在生成3D频谱图", unit="文件"):
        success, result = plot_spectrogram_3d(audio_file, output_dir)
        if success:
            success_count += 1
        else:
            error_messages.append(result)

    # 显示处理结果
    result_message = f"处理完成!\n\n成功处理: {success_count} 个文件"
    if error_messages:
        result_message += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        # 保存错误日志
        log_path = os.path.join(output_dir, "processing_errors.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(error_messages))

    messagebox.showinfo("处理结果", result_message)

    # 完成后打开输出文件夹
    if os.name == 'nt':  # Windows
        os.startfile(output_dir)
    elif os.name == 'posix':  # macOS/Linux
        os.system(f'open "{output_dir}"' if sys.platform == 'darwin' else f'xdg-open "{output_dir}"')




def select_directory_3d(title="选择文件夹", initialdir=None):
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    folder_path = filedialog.askdirectory(title=title, initialdir=initialdir)
    root.destroy()
    return folder_path if folder_path else None
    
    
def select_directory_centroid(title="选择文件夹", initialdir=None):
    """
    弹出文件夹选择对话框（频谱质心分析用）
    """
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    folder_path = filedialog.askdirectory(title=title, initialdir=initialdir)
    root.destroy()
    return folder_path if folder_path else None


def analyze_audio_file_centroid(audio_path, output_dir):

    try:

        filename = Path(audio_path).stem
        output_image = Path(output_dir) / f"{filename}_频谱质心分析.png"

        print(f"正在分析: {Path(audio_path).name}...")


        y, sr = librosa.load(audio_path)


        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]


        frames = range(len(spectral_centroids))
        t = librosa.frames_to_time(frames, sr=sr)


        plt.figure(figsize=(14, 10), dpi=120)
        plt.suptitle(f'音频分析: {filename}', fontsize=16, fontweight='bold')


        plt.subplot(3, 1, 1)
        librosa.display.waveshow(y, sr=sr, alpha=0.6, color='b')
        plt.title('音频波形', fontsize=12)
        plt.xlabel('时间 (秒)')
        plt.ylabel('振幅')
        plt.xlim(0, t.max())
        plt.grid(True, linestyle='--', alpha=0.7)


        plt.subplot(3, 1, 2)
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title('频谱图', fontsize=12)
        plt.xlabel('时间 (秒)')
        plt.ylabel('频率 (Hz)')


        plt.subplot(3, 1, 3)
        plt.plot(t, spectral_centroids, color='r', linewidth=2, label='Spectral Centroid')
        plt.fill_between(t, spectral_centroids, alpha=0.3, color='r')


        avg_centroid = np.mean(spectral_centroids)
        plt.axhline(y=avg_centroid, color='g', linestyle='--',
                    label=f'Average: {avg_centroid:.1f} Hz')

        plt.title('频谱质心图', fontsize=12)
        plt.xlabel('时间 (秒)')
        plt.ylabel('频率 (Hz)')
        plt.ylim(0, sr / 2)  # 设置频率范围为0到奈奎斯特频率
        plt.legend(loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.7)


        plt.tight_layout()
        plt.subplots_adjust(top=0.92)  # 为标题留出空间
        plt.savefig(output_image, bbox_inches='tight')
        plt.close()

        print(f"分析完成! 结果已保存至: {output_image}")
        print(f"平均频谱质心: {avg_centroid:.2f} Hz\n")
        return True, str(output_image)

    except Exception as e:
        error_msg = f"处理文件 {audio_path} 时出错: {str(e)}"
        print(error_msg)
        return False, error_msg


def batch_analyze_audio_centroid(input_dir, output_dir):


    Path(output_dir).mkdir(parents=True, exist_ok=True)


    audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']


    audio_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if Path(file).suffix.lower() in audio_extensions:
                audio_files.append(os.path.join(root, file))

    if not audio_files:
        messagebox.showwarning("警告", "未找到任何支持的音频文件 (.wav, .mp3, .flac, .ogg, .m4a, .aac)")
        return



    success_count = 0
    error_messages = []

    for audio_file in tqdm(audio_files, desc="正在生成频谱质心分析", unit="文件"):
        success, result = analyze_audio_file_centroid(audio_file, output_dir)
        if success:
            success_count += 1
        else:
            error_messages.append(result)

    # 显示处理结果
    result_message = f"处理完成!\n\n成功处理: {success_count} 个文件"
    if error_messages:
        result_message += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        # 保存错误日志
        log_path = os.path.join(output_dir, "processing_errors.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(error_messages))

    messagebox.showinfo("处理结果", result_message)

    # 完成后打开输出文件夹
    if os.name == 'nt':  # Windows
        os.startfile(output_dir)
    elif os.name == 'posix':  # macOS/Linux
        os.system(f'open "{output_dir}"' if sys.platform == 'darwin' else f'xdg-open "{output_dir}"')
    
    
    