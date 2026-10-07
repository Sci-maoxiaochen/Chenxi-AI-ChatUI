import os
import var


def get_skin():
    """获取当前皮肤名称"""
    return getattr(var, "CURRENT_SKIN", "default")


def set_skin(skin_name):
    """设置当前皮肤名称"""
    var.CURRENT_SKIN = skin_name


def list_skins():
    """扫描 skins 目录下所有可用皮肤"""
    skins_dir = "skins"
    if not os.path.exists(skins_dir):
        return ["default"]

    skins = [d for d in os.listdir(skins_dir) if os.path.isdir(os.path.join(skins_dir, d))]
    return skins if skins else ["default"]