#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LPK自动解包程序
删改自 https://github.com/ihopenot/LpkUnpacker
1、只保留了LPK解包功能，选择文件夹后自动递归扫描所有LPK文件并解包
2、减少目录层数，直接用读取的LPK原名拼接源文件夹名作为解包文件夹名
3、每个LPK解包文件夹内复制了预览图方便查看
4、解决错误闪退问题，错误解包文件会自动复制源文件夹到error子文件夹并写入错误信息
"""
from __future__ import unicode_literals
import json
import logging
import os
import shutil
import sys
import tkinter as tk
from datetime import datetime
from os import system
from tkinter import filedialog, messagebox
from lpk_loader import LpkLoader
from utils import safe_mkdir, normalize

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AutoUnpacker")


def select_directory():
    """选择要扫描的文件夹"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    print("请选择包含LPK文件的文件夹...")
    folder_path = filedialog.askdirectory(
        title="选择包含LPK文件的文件夹",
        mustexist=True
    )
    if not folder_path:
        print("未选择文件夹，程序退出")
        sys.exit(0)
    root.destroy()
    return folder_path


def find_lpk_files(folder_path):
    """递归查找文件夹中的所有LPK文件"""
    lpk_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.lpk'):
                file_path = os.path.join(root, file)
                lpk_files.append(file_path)
    return lpk_files


def copy_failed_source_to_error(lpk_path, output_base_dir, error_reason=None):
    """将失败的源文件夹复制到错误目录"""
    try:
        # 创建错误目录
        error_dir = os.path.join(output_base_dir, "error")
        safe_mkdir(error_dir)
        # 确定源文件夹（LPK文件所在的目录）
        source_dir = os.path.dirname(lpk_path)
        if not os.path.exists(source_dir):
            print(f"  源文件夹不存在: {source_dir}")
            return False
        # 生成目标目录名（使用源文件夹名）
        source_dir_name = os.path.basename(source_dir)
        if not source_dir_name:
            source_dir_name = "unknown_source"
        # 避免目录名冲突
        dest_dir = os.path.join(error_dir, source_dir_name)
        counter = 1
        while os.path.exists(dest_dir):
            dest_dir = os.path.join(error_dir, f"{source_dir_name}_{counter}")
            counter += 1
        # 复制整个源文件夹
        print(f"  复制失败源文件夹到: {os.path.relpath(dest_dir, output_base_dir)}")
        shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
        # 在错误目录中创建说明文件
        error_info_path = os.path.join(dest_dir, "000error_info.txt")
        with open(error_info_path, 'w', encoding='utf-8') as f:
            f.write(f"Failed LPK: {lpk_path}\n")
            f.write(f"Source directory: {source_dir}\n")
            f.write(f"Copied to error directory at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if error_reason:
                f.write(f"\nError reason: {error_reason}\n")
        return True
    except Exception as e:
        print(f"  复制失败源文件夹时出错: {e}")
        return False


def extract_lpk_file(lpk_path, config_path, output_dir, item_index, total_items):
    """解包单个LPK文件，返回 (success, error_message)"""
    try:
        print(f"[{item_index}/{total_items}] 解包: {os.path.basename(lpk_path)}")
        if config_path:
            print(f"  使用配置文件: {os.path.basename(config_path)}")
        # 尝试从config.json获取title等信息（用于确定目录名）
        sub_dir = None
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    title = normalize(config_data['title'])
                    file_id = str(config_data['fileId'])
                    preview_file = config_data['previewFile']
                    output_name = title + " " + file_id
                    sub_dir = os.path.join(output_dir, output_name)
            except Exception as e:
                print(f"  读取config.json失败: {e}")

        # 解包LPK文件（直接解包到输出目录）
        loader = LpkLoader(lpk_path, config_path)
        loader.extract(sub_dir)

        # 复制预览图片（放到目标目录，保持原文件名）
        lpk_dir = os.path.dirname(lpk_path)
        preview_path = os.path.join(lpk_dir, preview_file)
        preview_dest = os.path.join(sub_dir, preview_file)
        try:
            shutil.copy2(preview_path, preview_dest)
            print(f"  复制预览图到 {sub_dir}/: {preview_file}")
        except Exception as e:
            print(f"  复制预览图失败: {e}")
        print(f"  解包完成!")
        print("-"*50)
        return True, None

    except Exception as e:
        error_msg = str(e)
        print(f"  解包失败: {error_msg}")
        try:
            shutil.rmtree(output_dir, ignore_errors=True)
            print(f"  已清理产生的空目录")
        except Exception as cleanup_error:
            print(f"  清理空目录时出错（可忽略）: {cleanup_error}")
        import traceback
        traceback.print_exc()
        return False, error_msg


def scan_and_extract(folder_path):
    """扫描文件夹并解包所有LPK文件"""
    if not os.path.exists(folder_path):
        print(f"错误: 文件夹不存在 - {folder_path}")
        return False
    # 设置输出目录
    folder_name = os.path.basename(folder_path.rstrip('/\\'))
    output_base_dir = os.path.join(os.path.dirname(folder_path), f"{folder_name}_extracted")
    safe_mkdir(output_base_dir)
    print(f"输出目录: {output_base_dir}")
    # 查找所有LPK文件
    print(f"正在扫描文件夹: {folder_path}")
    lpk_files = find_lpk_files(folder_path)
    if not lpk_files:
        print("未找到LPK文件!")
        return False
    print(f"找到 {len(lpk_files)} 个LPK文件")
    # 解包每个LPK文件
    success_count = 0
    failed_files = []
    for i, lpk_path in enumerate(lpk_files, 1):
        config_path = os.path.join(os.path.dirname(lpk_path), "config.json")
        success, error_msg = extract_lpk_file(
            lpk_path, 
            config_path, 
            output_base_dir,
            i, 
            len(lpk_files)
        )
        if success:
            success_count += 1
        else:
            failed_files.append(os.path.basename(lpk_path))
            # 复制失败的源文件夹到错误目录
            print(f"  处理失败文件，复制源文件夹...")
            copy_failed_source_to_error(lpk_path, output_base_dir, error_msg)
    # 显示结果
    print("\n" + "="*50)
    print("解包完成!")
    print(f"源文件夹: {folder_path}")
    print(f"输出文件夹: {output_base_dir}")
    print(f"总计LPK文件: {len(lpk_files)}")
    print(f"成功解包: {success_count}")
    print(f"失败: {len(lpk_files) - success_count}")
    if failed_files:
        print("失败的文件:")
        for failed_file in failed_files:
            print(f"  - {failed_file}")
    print("="*50)
    return success_count > 0


def main():
    """主函数"""
    print("LPK 自动解包程序")
    print("="*50)
    # 选择文件夹
    folder_path = select_directory()
    if not folder_path:
        return
    print(f"已选择文件夹: {folder_path}")
    # 确认操作
    root = tk.Tk()
    root.withdraw()
    confirm = messagebox.askyesno(
        "确认操作",
        f"即将扫描文件夹:\n{folder_path}\n\n扫描所有LPK文件并自动解包。\n\n是否继续？"
    )
    if not confirm:
        print("用户取消操作")
        return
    # 开始扫描和解包
    try:
        success = scan_and_extract(folder_path)
        if success:
            messagebox.showinfo("解包完成", "LPK文件解包完成！\n请查看输出目录中的提取结果。")
        else:
            messagebox.showwarning("解包完成", "解包完成，但部分文件可能失败。\n请查看控制台输出获取详细信息。")
    except Exception as e:
        messagebox.showerror("错误", f"解包过程中发生错误:\n{str(e)}")
    print("程序结束")

if __name__ == "__main__":
    main()