import torch
import os
import sys

if len(sys.argv) != 2:
    print("用法: python resave_model.py <模型文件路径>")
    sys.exit(1)

model_path = sys.argv[1]

if not os.path.exists(model_path):
    print(f"错误: 文件 '{model_path}' 不存在。")
    sys.exit(1)

print(f"正在加载旧格式模型文件: {model_path}")
state_dict = torch.load(model_path, map_location="cpu")

new_model_path = model_path.replace('.bin', '.safe.bin')
print(f"正在将模型重新保存为新格式: {new_model_path}")
torch.save(state_dict, new_model_path, _use_new_zipfile_serialization=True)

print("重新保存成功！")
