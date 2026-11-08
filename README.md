# 微信输入法词库离线提取

从微信输入法 Windows **3.0.2.29** 官方安装包离线提取的词库样本、文本结果及可复现解析程序。

## 文件

| 文件 | 内容 |
| --- | --- |
| [全部词条_30317.txt](全部词条_30317.txt) | 从 kind=443 压缩 Trie 解码的 30,317 个词条 |
| [kind440匹配词条_13362.txt](kind440匹配词条_13362.txt) | 与 kind=440 哈希表匹配的 13,362 个词条 |
| [cell_dict.ssrc.zh](cell_dict.ssrc.zh) | 原始词库，319,557 字节 |
| [export_wetype_words.py](export_wetype_words.py) | 离线解析与导出程序 |
| [cityhash64.py](cityhash64.py) | CityHash64 实现，文件内保留上游许可 |
| [解析校验.json](解析校验.json) | 文件校验值、Trie 结构及匹配统计 |
| [文件校验.json](文件校验.json) | 原始提取结果各文件的 SHA-256 |
| [说明.md](说明.md) | 来源、方法、校验结果和复现说明 |

TXT 使用 UTF-8 BOM 编码，每行一个词条，排序且不重复。词条可能包含粗俗、暴力、色情及其他敏感表达；保留原始数据以便复核。

kind=440 表共有 13,386 个不同的校验哈希，其中 **24 个未匹配到明文词条**。这份结果不表示完整还原了该哈希表，也不能仅凭类型编号推断词条在输入法中的具体处理行为。

## 复现

需要 Python 3，无第三方依赖：

```bash
python export_wetype_words.py -f cell_dict.ssrc.zh -o all_words.txt --kind440-output kind440_words.txt --report report.json
```

## 样本来源

[微信输入法官方安装包 3.0.2.29](https://download.z.weixin.qq.com/app/win/WeTypeSetup_3.0.2.29.exe)

- 安装包 SHA-256：`39fdbe6aa0895152e580e47971f9bc059c8b14d85520b384db6878fc2ec4c495`
- 原始词库 MD5：`6555417414533a29960c3a4a01ad1303`
- 原始词库 SHA-256：`0a5ac7d40a6b639f422eb97664d574a2e99ee63b03136a6ee6733a98c2887ffb`

提取期间未安装微信输入法或 7-Zip。下载的安装包与临时解包工具已清理，未上传至本仓库。
