# Chenxi-AI-ChatUI
A Simple and Unadorned ChatUI

一个朴实无华的AI对话UI

*本项目使用AI辅助开发，不喜勿喷！*

## 如何使用？

### 对于Windows

1.从 **Releases** 下载zip（Windows 下载chenxi-AI-ChatUI-Windows.zip，Linux下载chenxi-AI-ChatUI-Linux.zip）


2.解压文件，双击运行 **init.exe**
### 对于Linux
1.从 **Releases** 下载zip（Windows 下载chenxi-AI-ChatUI-Windows.zip，Linux下载chenxi-AI-ChatUI-Linux.zip）

2.解压文件，**右键在此打开终端**

3.输入以下命令

```
python3 int.py
```

## 如何配置？

### 基础配置

1.右键桌宠，点击“AI 模型与项目设置”

2.分别填写“对话模型”和“识图模型”（若不需要导入自己的预设，则不需要配置识图模型），然后保存配置

然后你就可以双击桌宠开始聊天啦！

### 进阶配置

> 当你右键打开菜单时，你会看到其他配置选项

#### 更换角色/皮肤

在这里，你可以选择AI要扮演的角色。

#### 如何配置角色/皮肤？

> 支持格式：png,jpg,gif。后期会支持live2d等

1.右键桌宠，点击“导入全新角色立绘”

2.填写角色名称（便于记住）

3.导入图片（可以拖拽图片到指定位置）

4.分配表情或动作。您可以自己配置，或者使用AI自动归类（需要先配置视觉模型）

4.填写角色预设提示词

5.完成保存并切换

### 目前已知问题

Q：怎么那么大张脸糊上去了？！

A：您只需要按住Ctrl的同时滚动鼠标滚轮即可缩放桌宠

Q：为什么我无法运行

A:目前已知问题是可能没有安装requests，输入以下命令

```
pip install requests
```
## 致谢
项目基于EggyUI Desktop Pet修改
https://github.com/PidanEggyTeam/EggyUI-Desktop-Pet
