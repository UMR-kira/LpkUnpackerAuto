#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LPK自动解包程序
1、只保留了LPK解包功能，选择文件夹后自动递归扫描所有LPK文件并解包
2、减少目录层数，不多余创建原id文件夹，直接创建LPK原名文件夹
3、每个LPK单独解包文件夹内复制了缩略图方便查看，并保留原文件夹名id文本和导出信息
4、解决错误闪退问题，错误解包文件会自动移动源文件夹到error子文件夹并写入错误信息文本
"""
from __future__ import unicode_literals

import json
import logging
import os
import re
import shutil
import sys
import tkinter as tk
import zipfile
from datetime import datetime
from hashlib import md5
from tkinter import filedialog, messagebox
from typing import List
from typing import Tuple

import filetype
from filetype import filetype
from filetype.types import Type

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


def find_config_file(lpk_path):
    """查找与LPK文件对应的config.json文件"""
    lpk_dir = os.path.dirname(lpk_path)
    # 检查可能的位置
    possible_locations = [
        os.path.join(lpk_dir, "config.json"),          # 同目录
        os.path.join(os.path.dirname(lpk_dir), "config.json")  # 父目录
    ]
    for config_path in possible_locations:
        if os.path.exists(config_path):
            return config_path
    return None


def find_preview_images(item_path):
    """查找目录中的预览图片（查找所有图片文件）"""
    preview_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    preview_images = []
    
    for root, dirs, files in os.walk(item_path):
        for file in files:
            file_lower = file.lower()
            if any(file_lower.endswith(ext) for ext in preview_extensions):
                preview_images.append(os.path.join(root, file))
    
    return preview_images


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
        error_info_path = os.path.join(dest_dir, "error_info.txt")
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


def get_existing_subdirs(directory):
    """获取目录中已存在的子目录列表"""
    if not os.path.exists(directory):
        return set()
    
    existing = set()
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            existing.add(item)
    return existing


def is_directory_empty(dir_path):
    """检查目录是否为空（无文件且无子目录）"""
    if not os.path.exists(dir_path):
        return True
    # 使用 os.scandir 更高效
    try:
        with os.scandir(dir_path) as it:
            return not any(True for _ in it)
    except (OSError, PermissionError):
        # 如果无法访问，假设非空
        return False


def cleanup_failed_directories(output_dir, existing_before):
    """清理解包失败后留下的空目录"""
    if not os.path.exists(output_dir):
        return
    # 找出解包后新增的目录
    current_dirs = get_existing_subdirs(output_dir)
    new_dirs = current_dirs - existing_before
    if not new_dirs:
        return
    cleaned_count = 0
    for dir_name in new_dirs:
        dir_path = os.path.join(output_dir, dir_name)
        if is_directory_empty(dir_path):
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                print(f"  清理空目录: {dir_name}")
                cleaned_count += 1
            except Exception as e:
                print(f"  清理目录 {dir_name} 失败: {e}")
    if cleaned_count > 0:
        print(f"  共清理 {cleaned_count} 个空目录")


def extract_lpk_file(lpk_path, config_path, output_dir, item_index, total_items):
    """解包单个LPK文件，返回 (success, error_message)"""
    try:
        lpk_name = os.path.splitext(os.path.basename(lpk_path))[0]
        # 记录解包前已存在的子目录
        existing_subdirs = get_existing_subdirs(output_dir)
        print(f"[{item_index}/{total_items}] 解包: {os.path.basename(lpk_path)}")
        if config_path:
            print(f"  使用配置文件: {os.path.basename(config_path)}")
        # 尝试从config.json获取title（用于确定子目录名）
        subdir_name = None
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    if 'title' in config_data:
                        subdir_name = normalize(config_data['title'])
                        print(f"  检测到项目标题: {config_data['title']}")
            except Exception as e:
                print(f"  读取config.json失败: {e}")
        # 解包LPK文件（直接解包到输出目录）
        loader = LpkLoader(lpk_path, config_path)
        loader.extract(output_dir)
        # 确定目标子目录
        target_dir = output_dir
        if subdir_name:
            # 检查LpkLoader是否创建了以subdir_name命名的子目录
            expected_dir = os.path.join(output_dir, subdir_name)
            if os.path.exists(expected_dir) and os.path.isdir(expected_dir):
                target_dir = expected_dir
                print(f"  使用子目录: {subdir_name}")
        target_dir_name = os.path.basename(target_dir)
        # 复制预览图片（放到目标目录，保持原文件名）
        lpk_dir = os.path.dirname(lpk_path)
        preview_images = find_preview_images(lpk_dir)
        if preview_images:
            for preview_path in preview_images:
                preview_filename = os.path.basename(preview_path)
                preview_dest = os.path.join(target_dir, preview_filename)
                try:
                    shutil.copy2(preview_path, preview_dest)
                    print(f"  复制预览图到 {target_dir_name}/: {preview_filename}")
                except Exception as e:
                    print(f"  复制预览图失败: {e}")
        # 创建源文件名字的无后缀空文件作为标记（放到目标目录）
        try:
            marker_filename = f"{lpk_name}"
            marker_path = os.path.join(target_dir, marker_filename)
            with open(marker_path, 'w', encoding='utf-8') as f:
                f.write(f"Source: {lpk_path}\nConfig: {config_path or 'None'}\nExtracted at: {os.path.abspath(target_dir)}")
            print(f"  创建标记文件到 {target_dir_name}/: {marker_filename}")
        except Exception as e:
            print(f"  创建标记文件失败: {e}")
        print(f"  解包完成!")
        return True, None
        
    except Exception as e:
        error_msg = str(e)
        print(f"  解包失败: {error_msg}")
        # 清理解包失败后留下的空目录
        try:
            cleanup_failed_directories(output_dir, existing_subdirs)
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
        config_path = find_config_file(lpk_path)
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


class LpkLoader:
    def __init__(self, lpkpath, configpath) -> None:
        self.lpkpath = lpkpath
        self.configpath = configpath
        self.lpkType = None
        self.encrypted = "true"
        self.trans = {}
        self.entrys = {}
        self.load_lpk()

    def load_lpk(self):
        self.lpkfile = zipfile.ZipFile(self.lpkpath)
        try:
            config_mlve_raw = self.lpkfile.read(hashed_filename("config.mlve")).decode()
        except KeyError:
            try:
                config_mlve_raw = self.lpkfile.read("config.mlve").decode('utf-8-sig')
            except:
                logger.fatal("Failed to retrieve lpk config!")
                exit(0)

        self.mlve_config = json.loads(config_mlve_raw)

        logger.debug(f"mlve config:\n {self.mlve_config}")
        self.lpkType = self.mlve_config.get("type")
        # only steam workshop lpk needs config.json to decrypt
        if self.lpkType == "STM_1_0":
            self.load_config()

    def load_config(self):
        self.config = json.loads(open(self.configpath, "r", encoding="utf8").read())

    def extract(self, outputdir: str):
        if self.lpkType in ["STD2_0", "STM_1_0"]:
            for chara in self.mlve_config["list"]:
                if self.lpkType == "STM_1_0" and hasattr(self, 'config') and 'title' in self.config:
                    chara_name = self.config["title"]
                else:
                    chara_name = chara["character"] if chara["character"] != "" else "character"
                subdir = os.path.join(outputdir, normalize(chara_name))
                safe_mkdir(subdir)

                for i in range(len(chara["costume"])):
                    logger.info(f"extracting {chara_name}_costume_{i}")
                    self.extract_costume(chara["costume"][i], subdir)

                # replace encryped filename to decrypted filename in entrys(model.json)
                for name in self.entrys:
                    out_s: str = self.entrys[name]
                    for k in self.trans:
                        out_s = out_s.replace(k, self.trans[k])
                    open(os.path.join(subdir, name), "w", encoding="utf8").write(out_s)
        else:
            try:
                print("Deprecated/unknown lpk format detected. Attempting with STD_1_0 format...")
                print("Decryption may not work for some packs, even though this script outputs all files.")
                self.encrypted = self.mlve_config.get("encrypt", "true")
                if self.encrypted == "false":
                    print("lpk is not encrypted, extracting all files...")
                    self.lpkfile.extractall(outputdir)
                    return
                # For STD_1_0 and earlier
                for file in self.lpkfile.namelist():
                    if os.path.splitext(file)[-1] == '':
                        continue
                    subdir = os.path.join(outputdir, os.path.dirname(file))
                    outputFilePath = os.path.join(subdir, os.path.basename(file))
                    safe_mkdir(subdir)
                    if os.path.splitext(file)[-1] in [".json", ".mlve", ".txt"]:
                        print(f"Extracting {file} -> {outputFilePath}")
                        self.lpkfile.extract(file, outputdir)
                    else:
                        print(f"Decrypting {file} -> {outputFilePath}")
                        decryptedData = self.decrypt_file(file)
                        with open(outputFilePath, "wb") as outputFile:
                            outputFile.write(decryptedData)
            except:
                logger.fatal(f"Failed to decrypt {self.lpkpath}, possibly wrong/unsupported format.")

    def extract_costume(self, costume: dict, dir: str):
        if costume["path"] == "":
            return

        filename: str = costume["path"]

        self.check_decrypt(filename)

        self.extract_model_json(filename, dir)

    def extract_model_json(self, model_json: str, dir):
        logger.debug(f"========= extracting model {model_json} =========")
        # already extracted
        if model_json in self.trans:
            return

        subdir = dir
        entry_s = self.decrypt_file(model_json).decode(encoding="utf8")
        entry = json.loads(entry_s)

        out_s = json.dumps(entry, ensure_ascii=False)
        id = len(self.entrys)

        self.entrys[f"model{id}.json"] = out_s

        self.trans[model_json] = f"model{id}.json"

        logger.debug(f"model{id}.json:\n{entry}")

        for name, val in travels_dict(entry):
            logger.debug(f"{name} -> {val}")
            # extract submodel
            if (name.lower().endswith("_command") or name.lower().endswith("_postcommand")) and val:
                commands: List[str] = val.split(";")
                for cmd in commands:
                    enc_file = find_encrypted_file(cmd)
                    if enc_file == None:
                        continue

                    if self.is_model_command(cmd):
                        enc_file = find_encrypted_file(cmd)
                        self.extract_model_json(enc_file, dir)
                    else:
                        name += f"_{id}"
                        name = self.name_change(name)
                        _, suffix = self.recovery(enc_file, os.path.join(subdir, name))
                        self.trans[enc_file] = name + suffix

            if is_encrypted_file(val):
                enc_file = val
                # already decrypted
                if enc_file in self.trans:
                    continue
                # recover regular files
                else:
                    name += f"_{id}"
                    name = self.name_change(name)
                    _, suffix = self.recovery(enc_file, os.path.join(subdir, name))
                    self.trans[enc_file] = name + suffix

        logger.debug(f"========= end of model {model_json} =========")

    def is_model_command(self, cmd: str):
        model_commands = ["change_cos", "change_model", "add_submodel", "remove_submodel"]
        for model_cmd in model_commands:
            if cmd.startswith(model_cmd):
                return True
        return False

    def check_decrypt(self, filename):
        '''
        Check if decryption work.

        If lpk earsed fileId in config.json, this function will automatically try to use lpkFile as fileId.
        If all attemptions failed, this function will read fileId from ``STDIN``.
        '''

        logger.info("try to decrypt entry model.json")

        try:
            self.decrypt_file(filename).decode(encoding="utf8")
        except UnicodeDecodeError:
            logger.info("trying to auto fix fileId")
            success = False
            possible_fileId = []
            possible_fileId.append(self.config["lpkFile"].strip('.lpk'))
            for fileid in possible_fileId:
                self.config["fileId"] = fileid
                try:
                    self.decrypt_file(filename).decode(encoding="utf8")
                except UnicodeDecodeError:
                    continue

                success = True
                break
            if not success:
                print(
                    "steam workshop fileid is usually a foler under PATH_TO_YOUR_STEAM/steamapps/workshop/content/616720/([0-9]+)")
                fileid = input("auto fix failed, please input fileid manually: ")
                self.config["fileId"] = fileid
                try:
                    self.decrypt_file(filename).decode(encoding="utf8")
                except UnicodeDecodeError:
                    logger.fatal("decrypt failed!")

    def recovery(self, filename, output) -> Tuple[bytes, str]:
        ret = self.decrypt_file(filename)
        suffix = guess_type(ret)
        print(f"recovering {filename} -> {output + suffix}")
        open(output + suffix, "wb").write(ret)
        return ret, suffix

    def getkey(self, file: str):
        if self.lpkType == "STM_1_0" and self.mlve_config["encrypt"] != "true":
            return 0
        if self.lpkType == "STM_1_0":
            return genkey(self.mlve_config["id"] + self.config["fileId"] + file + self.config["metaData"])
        elif self.lpkType == "STD2_0":
            return genkey(self.mlve_config["id"] + file)
        elif self.lpkType == "STD_1_0":
            return genkey(self.mlve_config["id"] + file)
        else:
            # return genkey("com.oukaitou.live2d.pro" + self.mlve_config["id"] + "cDaNJnUazx2B4xCYFnAPiYSyd2M=\n")
            # else:
            raise Exception(f"not support type {self.mlve_config['type']}")

    def decrypt_file(self, filename) -> bytes:
        data = self.lpkfile.read(filename)
        return self.decrypt_data(filename, data)

    def decrypt_data(self, filename: str, data: bytes) -> bytes:
        key = self.getkey(filename)
        return decrypt(key, data)

    def name_change(self, name: str) -> str:
        # 去除name里面的FileReferences_
        name = name.replace("FileReferences_", "")
        return name.replace("\\", "/")


# utils
def hashed_filename(s: str) -> str:
    t = md5()
    t.update(s.encode())
    return t.hexdigest()


def normalize(s: str) -> str:
    s = ''.join(c for c in s if ord(c) >= 32 or c == ' ')
    s = re.sub(r'[<>:"|?*]', '', s)
    if not s.strip():
        s = "unnamed"
    return s


def safe_mkdir(s: str):
    # Create the directory
    os.makedirs(s, exist_ok=True)
    print(f"Created directory: {s}")


def genkey(s: str) -> int:
    ret = 0
    for i in s:
        ret = (ret * 31 + ord(i)) & 0xffffffff
    if ret & 0x80000000:
        ret = ret | 0xffffffff00000000
    return ret


def decrypt(key: int, data: bytes) -> bytes:
    ret = []
    for slice in [data[i:i + 1024] for i in range(0, len(data), 1024)]:
        tmpkey = key
        for i in slice:
            tmpkey = (65535 & 2531011 + 214013 * tmpkey >> 16) & 0xffffffff
            ret.append((tmpkey & 0xff) ^ i)
    return bytes(ret)


match_rule = re.compile(r"[0-9a-f]{32}.bin3?")


def is_encrypted_file(s: str) -> bool:
    if type(s) != str:
        return False
    if match_rule.fullmatch(s) != None:
        return True
    return False


# find all enc_file in s
def find_encrypted_file(s: str) -> str:
    files = re.findall(match_rule, s)
    if files == []:
        return None
    return files[0]


def get_encrypted_file(s: str):
    if type(s) != str:
        return None
    if s.startswith("change_cos"):
        filename = s[len("change_cos "):]
    else:
        filename = s
    if not is_encrypted_file(filename):
        return None
    return filename


def travels_dict(dic: dict):
    for k in dic:
        if type(dic[k]) == dict:
            for p, v in travels_dict(dic[k]):
                yield f"{k}_{p}", v
        elif type(dic[k]) == list:
            for p, v in travels_list(dic[k]):
                yield f"{k}_{p}", v
        else:
            yield str(k), dic[k]


def travels_list(vals: list):
    for i in range(len(vals)):
        if type(vals[i]) == dict:
            for p, v in travels_dict(vals[i]):
                yield f"{i}_{p}", v
        elif type(vals[i]) == list:
            for p, v in travels_list(vals[i]):
                yield f"{i}_{p}", v
        else:
            yield str(i), vals[i]


class Moc3(Type):
    MIME = "application/moc3"
    EXTENSION = "moc3"
    def __init__(self):
        super(Moc3, self).__init__(mime=Moc3.MIME, extension=Moc3.EXTENSION)
    def match(self, buf):
        return len(buf) > 3 and buf.startswith(b"MOC3")


class Moc(Type):
    MIME = "application/moc"
    EXTENSION = "moc"
    def __init__(self):
        super(Moc, self).__init__(mime=Moc.MIME, extension=Moc.EXTENSION)
    def match(self, buf):
        return len(buf) > 3 and buf.startswith(b"moc")

filetype.add_type(Moc3())
filetype.add_type(Moc())
def guess_type(data: bytes):
    ftype = filetype.guess(data)
    if ftype != None:
        return "." + ftype.extension
    try:
        json.loads(data.decode("utf8"))
        return ".json"
    except:
        return ""


if __name__ == "__main__":
    main()