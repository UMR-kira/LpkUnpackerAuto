# LPK自动解包程序

删改自 https://github.com/ihopenot/LpkUnpacker

1、只保留了LPK解包功能，选择文件夹后自动递归扫描所有LPK文件并解包

2、减少目录层数，直接用读取的LPK标题拼接源id名作为解包文件夹名

3、每个LPK解包文件夹内复制了源文件预览图方便查看

4、解决错误闪退问题，错误解包文件会自动复制源文件夹到error子文件夹并写入错误信息


# LpkUnpacker

这个工具用来解包Live2dViewerEx的LPK文件

如果你在使用工具时遇到任何困难，请先查询'[Issues](https://github.com/ihopenot/LpkUnpacker/issues)'中的内容

*增加了对STD_1_0以及之前的格式支持
注意，少部分的早期lpk仍然无法解包，推测可能存在未知的密钥生成或解密算法
