import argparse
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NSMAP = {"w": W_NS}

NAMESPACES = {
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "aink": "http://schemas.microsoft.com/office/drawing/2016/ink",
    "am3d": "http://schemas.microsoft.com/office/drawing/2017/model3d",
    "o": "urn:schemas-microsoft-com:office:office",
    "oel": "http://schemas.microsoft.com/office/2019/extlst",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": M_NS,
    "v": "urn:schemas-microsoft-com:vml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w": W_NS,
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16sdtdh": "http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
}
XML_SPACE_NS = "http://www.w3.org/XML/1998/namespace"

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


@dataclass(frozen=True)
class Replacement:
    label: str
    index: int
    locator: str
    replacement: str


def normalize_text(text: str) -> str:
    return re.sub(r"[\s\u3000]+", "", text or "")


def paragraph_text(p_elem: ET.Element) -> str:
    return "".join(t.text or "" for t in p_elem.findall(".//w:t", NSMAP)).strip()


def paragraph_has_math(p_elem: ET.Element) -> bool:
    return (
        p_elem.find(f".//{{{M_NS}}}oMath") is not None
        or p_elem.find(f".//{{{M_NS}}}oMathPara") is not None
    )


def rewrite_paragraph_text_preserve_runs(p_elem: ET.Element, new_text: str) -> bool:
    text_elems = p_elem.findall(".//w:t", NSMAP)
    if not text_elems:
        return False
    text_elems[0].text = new_text
    text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
    for text_elem in text_elems[1:]:
        text_elem.text = ""
    return True


def rewrite_run_text_preserve_text_nodes(run_elem: ET.Element, new_text: str) -> bool:
    text_elems = run_elem.findall(".//w:t", NSMAP)
    if not text_elems:
        return False
    text_elems[0].text = new_text
    text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
    for text_elem in text_elems[1:]:
        text_elem.text = ""
    return True


def rewrite_paragraph_preserve_math_runs(p_elem: ET.Element, run_texts: list[str]) -> bool:
    runs = [child for child in list(p_elem) if child.tag == f"{{{W_NS}}}r"]
    if len(runs) != len(run_texts):
        return False
    for run_elem, new_text in zip(runs, run_texts):
        if not rewrite_run_text_preserve_text_nodes(run_elem, new_text):
            return False
    return True


REPLACEMENTS = [
    Replacement(
        "中文摘要-1",
        10,
        "明胶是由动物皮、骨等富含胶原蛋白的组织经部分水解所得的天然高分子材料",
        "明胶是一种重要的天然高分子材料，但天然明胶普遍存在凝胶强度偏低、耐水性不足等性能局限。鹿皮作为非传统明胶原料，其改性调控规律尚缺乏系统研究。本研究以鹿皮明胶（DSG）为研究对象，分别采用二醛淀粉（DAS）和谷氨酰胺转氨酶（TGase）对其进行改性处理，并以未改性猪皮明胶（PSG）作为阳性对照。",
    ),
    Replacement(
        "中文摘要-2",
        11,
        "本研究以鹿皮明胶（DSG）为研究对象",
        "通过筛选改性条件，测定凝胶强度、乳化活性指数（EAI）、乳化稳定性指数（ESI）、持水率（WHC）及持油率（OHC）等功能指标，结合紫外吸收光谱（UV）和傅里叶变换红外光谱（FTIR）表征结构变化，系统评价两种改性方式对鹿皮明胶性能的影响。结果显示，DAS 和 TGase 改性均显著降低了鹿皮明胶的溶胀率和溶失率，增强了网络的水稳定性。",
    ),
    Replacement(
        "中文摘要-3",
        12,
        "结果表明，在改性条件筛选阶段",
        "在功能特性方面，DAS-DSG 的凝胶强度最高，为（276.40±7.56）g，显著高于 TG-DSG（251.80±4.81）g、PSG（218.53±5.01）g 及 DSG（187.37±5.73）g；DAS-DSG 的乳化活性指数最高，而 TG-DSG 的乳化稳定性指数最高。两种改性明胶的持水率和持油率均显著高于 DSG 和 PSG。结构表征显示，两种改性处理均引起明胶分子构象重排，其中 DAS-DSG 的结构响应更为显著，且分子间氢键作用增强。本研究为鹿皮明胶的改性调控与开发利用提供了理论依据。",
    ),
    Replacement(
        "1.1.1-1",
        62,
        "明胶是一种由胶原蛋白水解降解获得的天然高分子生物材料。",
        "明胶是一种由胶原蛋白水解降解获得的天然高分子生物材料。胶原蛋白是动物结缔组织中含量最丰富的结构蛋白。经酸、碱或热化学方法处理后，其三螺旋结构被破坏，并部分水解为可溶性蛋白聚合物，该产物即为明胶。明胶分子主要由不同长度的肽链组成，这些链在适宜条件下可通过氢键和疏水相互作用形成三维凝胶网络，从而赋予其特有的凝胶性能。由于具有良好的生物相容性、生物可降解性、成膜性和凝胶性，明胶在食品、医药和生物材料等领域被广泛研究与应用[1]。明胶的利用可追溯至古代。15 世纪时，英国已开始利用牛蹄等动物副产物提取胶状物；1681 年，法国发明家 Denis Papin 提出了骨胶提取技术；1812 年，法国化学家 Jean-Pierre-Joseph d’Arcet 改良了提胶工艺，并引入酸性预处理以提高提取效率；19 世纪中叶，美国开始工业化生产粉状明胶产品，从而极大拓展了其应用范围[2]。",
    ),
    Replacement(
        "1.1.1-2",
        63,
        "现代科研对明胶的结构与功能进行了深入分析。",
        "现代研究已对明胶的结构与功能开展了较为深入的分析。明胶的理化性质主要受原料来源和预处理方法影响。原料来源决定其氨基酸组成、分子量分布及三螺旋片段的保留程度，进而影响凝胶强度、熔融温度、黏度和成膜性能；预处理方法则通过改变胶原蛋白的断裂方式和降解程度，进一步影响明胶的等电点、分子链完整性及最终功能特性[3]。根据原料来源，明胶主要可分为猪皮明胶、牛皮（牛骨）明胶和鱼皮明胶。（1）猪皮明胶通常具有较高的凝胶强度和较好的加工适应性，且生产工艺成熟、成本相对较低，因此在食品和药用明胶领域应用广泛，但其使用受到宗教禁忌限制，并且在部分高湿环境中的稳定性有限；（2）牛源明胶的热稳定性和结构稳定性相对较好，常用于药用胶囊、食品加工和部分工业材料，但其生产周期较长、成本较高；（3）鱼皮明胶具有来源广、宗教适应性强和生物安全性较好的特点，在功能食品、可食用膜和替代性包装材料中具有明显优势，但由于其脯氨酸和羟脯氨酸含量通常较低，往往表现出凝胶强度偏低、熔融温度较低和热稳定性不足等问题，从而限制了其在高强度凝胶体系中的直接应用[4-6]。",
    ),
    Replacement(
        "1.1.1-3",
        64,
        "按预处理方法划分，明胶通常可分为 A 型明胶和 B 型明胶。",
        "按预处理方法划分，明胶通常可分为 A 型明胶和 B 型明胶。预处理方式的差异会改变胶原纤维的溶胀与断裂路径。酸法处理对分子主链的破坏相对较小，而碱法处理会引起更明显的脱酰胺和结构重排，因此两者在分子量分布、等电点及凝胶行为上存在系统差异[7]。（1）A 型明胶通常由酸法预处理获得，原料多为猪皮，也包括部分鱼皮原料。该类明胶等电点较高，一般在 pH 8–9 左右，分子链完整性相对较好，较易保留 α 链和部分高分子组分，因此常表现出较好的溶解性、透明度和加工适应性，在食品、药品和化妆品等领域应用较多。（2）B 型明胶通常由碱法预处理获得，常见原料为牛皮或牛骨，其等电点通常在 pH 4–5 左右。由于碱处理时间较长，脱酰胺作用更明显，其电荷性质、黏弹行为和凝胶特征与 A 型明胶存在差异。相较而言，B 型明胶在某些体系中表现出更高的结构稳定性，但加工周期较长，工艺负担也更重[8]。",
    ),
    Replacement(
        "1.1.2-总述",
        66,
        "天然明胶中含有较多亲水性基团",
        "天然明胶含有较多亲水性基团，其网络结构主要依赖较弱的非共价作用维持，因此常表现出耐水性差、吸湿性强、热稳定性不足和机械性能有限等问题[9]。在高湿或受热条件下，这些缺陷会进一步导致材料发生溶胀、软化甚至部分溶解，从而影响其结构稳定性和使用性能[10]。为改善上述问题，相关研究引入了明胶改性技术，即通过物理、化学、酶促或复合等方法调控明胶的分子链结构、分子间作用力及网络形态，以提高其稳定性和功能性[11,12]。从研究发展过程看，早期改性主要集中于增塑、共混和交联等基础处理，随后逐步扩展到纳米增强、活性组分引入和多机制协同调控等方向[13,14]。目前，明胶改性方法主要包括物理改性、化学改性、酶促改性和复合改性[15]。",
    ),
    Replacement(
        "1.1.2.1-1",
        68,
        "物理改性是指在不引入化学试剂或形成新的化学键的条件下",
        "物理改性是指在不引入化学试剂、且不形成新的化学键的条件下，通过物理手段改变明胶分子的结构或分布状态。常见方法包括超声处理、高压处理和辐照处理等，其本质是利用外界能量作用于明胶分子，使其构象发生变化或改善分子间作用，从而改变材料的热力学或力学特性。",
    ),
    Replacement(
        "1.1.2.1-2",
        69,
        "物理改性技术作为最早开展的改性方式之一",
        "物理改性技术是最早开展的明胶改性方式之一。Sezer 等人在鱼明胶高静水压和超声处理研究中发现，这类非化学改性手段能够改变分子链排列、氢键数量及局部微结构，进而影响明胶溶液的物理特性和凝胶性能[16]。近年来，多种新型物理改性方法被用于改善明胶性能。Li 等人报道，超声处理可显著调节明胶乳液的物理性质，并改善其凝胶强度、热稳定性及流变行为，表明超声可通过空化效应和机械效应改变明胶分子间相互作用[17]。Refat 等人采用超声辅助提取改善鱼鳞明胶的功能特性，该处理对凝胶性能的增强也可视为物理能量输入改变胶原结构的一种改性方式[18]。此外，已有研究通过改变明胶薄膜的紫外辐照时间观察其微观结构变化，结果显示紫外线可引发明胶交联反应，进而提高材料的物理性能[18,19]。总体来看，物理改性在改善明胶体系物理特性方面具有一定效果，但由于通常难以形成稳定的分子间化学结合，因此其对耐水性和长期结构稳定性的提升往往有限。",
    ),
    Replacement(
        "1.1.2.3-1",
        80,
        "复合改性是指将两种及以上改性手段或功能组分协同应用于明胶体系中",
        "复合改性是指将两种及以上改性手段或功能组分协同应用于明胶体系中，通过多重作用共同调控其结构与性能的一类改性方式。与单一改性相比，复合改性更强调不同改性因素之间的协同效应，因此近年来被认为是提升明胶综合性能的重要发展方向。",
    ),
    Replacement(
        "1.1.2.3-2",
        81,
        "近年来，复合改性在明胶材料中的应用明显增多。",
        "近年来，复合改性在明胶材料中的应用明显增多。Wang 等人通过漆酶催化紫花椰菜提取物交联，并结合 Zn-carbon dots 对明胶膜进行复合处理，结果表明该方法能够同时提高明胶薄膜的理化性能和功能特性，显示出复合改性在智能活性包装中的应用优势[33]。但复合改性也存在一定局限。由于其通常涉及多种改性因素共同作用，体系设计和工艺控制相对更为复杂，不同组分之间的相容性、作用顺序及处理条件都会影响最终效果。因此，在实际应用中仍需根据目标性能对改性体系进行合理设计与优化。",
    ),
    Replacement(
        "1.1.3-1",
        83,
        "明胶的制备是指以动物皮、骨、鳞等富含胶原的组织为原料",
        "明胶的制备是指以动物皮、骨、鳞等富含胶原的组织为原料，在一定预处理和提取条件下，使天然胶原发生部分变性和降解，并进一步转化为可溶性明胶的过程。其本质在于通过外界处理破坏胶原蛋白原有的高级结构和分子间作用，使其在热作用下逐步溶出，并形成具有一定功能特性的明胶产物。",
    ),
    Replacement(
        "1.1.3-2",
        84,
        "从整体工艺来看，明胶制备通常包括原料预处理、酸或碱处理、热提取、过滤纯化、浓缩和干燥等步骤。",
        "从整体工艺来看，明胶制备通常包括原料预处理、酸或碱处理、热提取、过滤纯化、浓缩和干燥等步骤。其中，前处理的主要作用是去除杂质并提高胶原的可提取性，后续提取过程则决定明胶的得率、分子结构及理化性质。当前研究普遍认为，不同制备方法之间的差异主要体现在前处理方式和提取条件上，而这些差异会进一步影响明胶的凝胶强度、热稳定性及功能特性[34-36]。",
    ),
    Replacement(
        "1.1.3-3",
        85,
        "在常见制备方法中，酸处理法和碱处理法仍然是明胶制备中最重要的两类传统方法",
        "在常见制备方法中，酸处理法和碱处理法仍是明胶制备中最重要的两类传统方法[37,38]。酸处理法是指利用酸性条件破坏胶原纤维中的分子间作用，使原料发生膨胀并有利于后续热提取，其特点是处理过程相对较快，适用于部分结构较易松散的胶原原料。碱处理法则是利用碱性条件去除非胶原成分并削弱胶原中较稳定的交联结构，从而提高后续提取效率。与酸处理法相比，碱处理法通常处理时间更长，但对部分交联程度较高的原料更为适用[39,40]。这两类方法工艺成熟、应用广泛，是目前明胶工业制备和实验研究中的主要基础路线。",
    ),
    Replacement(
        "1.1.3-4",
        86,
        "除传统酸碱法外，酶法辅助制备近年来也受到较多关注。",
        "除传统酸碱法外，酶法辅助制备近年来也受到较多关注。酶法制备是指利用蛋白酶等生物催化剂对原料中的胶原结构进行适度水解，以促进明胶溶出并提高提取效率。与传统酸碱处理相比，酶法通常反应条件更为温和，在一定程度上有助于减少过度降解，并改善所得明胶的功能性质[41]。同时，超声、高压、微波和亚临界水等绿色提取技术也被用于提高明胶制备效率[42]。这类方法通常是在传统制备工艺基础上引入额外辅助条件，其主要目的是缩短处理时间、提高提取率或改善最终产品性能。总体来看，明胶制备方法的选择会直接影响产品得率、结构特征和功能性质。因此，在实际制备过程中，应结合原料特点和目标性能对制备条件进行合理选择与优化。",
    ),
    Replacement(
        "1.2-1",
        89,
        "明胶作为一种来源广泛的天然高分子材料",
        "明胶作为一种来源广泛的天然高分子材料，在食品、医药及包装等领域具有较高的应用价值和较大的市场需求。现阶段，明胶的工业化生产仍主要依赖猪、牛等传统动物皮骨资源，其原料供应在一定程度上受到动物疫病和宗教饮食限制等因素的影响。与此同时，天然明胶还存在热稳定性不足、易吸水膨胀、易溶解及力学性能有限等问题。这些不足使其在部分应用条件下难以保持稳定性能，也限制了其进一步开发利用。因此，围绕明胶性能缺陷开展改性调控研究，已成为明胶基础研究和应用研究中的重要内容。",
    ),
    Replacement(
        "1.2-2",
        90,
        "梅花鹿鹿皮中含有丰富的胶原蛋白资源",
        "梅花鹿鹿皮富含胶原蛋白资源，具备制备明胶的物质基础，是传统畜源明胶之外值得关注的新型原料来源之一。与猪皮、牛皮及鱼皮等研究较多的明胶原料相比，鹿皮明胶的相关研究总体较少，尤其在改性调控方面尚缺乏系统探索。目前，关于明胶改性的研究主要集中于常见原料来源，而针对鹿皮明胶改性后结构变化、功能特性变化及其作用规律的研究尚未见报道。基于此，本研究拟以鹿皮明胶为研究对象，围绕其改性调控开展系统研究。通过采用不同改性技术对鹿皮明胶进行处理，并结合其结构特征和功能性质的变化，分析和比较不同改性方式对鹿皮明胶性能的影响，从而探究不同改性处理对鹿皮明胶性质的调控作用，为后续改性方式筛选及性能优化提供理论依据。",
    ),
    Replacement(
        "2.2.1-1",
        98,
        "各组样品均准确称取 0.200 g 鹿皮明胶",
        "各组样品均准确称取 0.200 g 鹿皮明胶。加入适量去离子水使其充分溶胀后，于 60 ℃ 水浴中磁力搅拌至完全溶解。根据不同处理方式向体系中加入相应改性剂或酶制剂，并采用 0.1 mol/L NaOH 或 0.1 mol/L HCl 调节至目标 pH。随后以去离子水定容至 3.30 mL，使明胶终质量浓度约为 6.0%（w/v）。反应结束后，将样品液转入培养皿中，于 −20 ℃ 预冻 24 h，再冷冻干燥 48 h，得到冻干凝胶样品备用。",
    ),
    Replacement(
        "2.2.1.1",
        100,
        "空白对照组（G组）在明胶完全溶解后",
        "空白对照组（G 组）在明胶完全溶解后，不添加任何改性剂或交联剂，直接以去离子水将体系总体积定容至 3.30 mL。混匀后将样品液转入培养皿中，按上述条件进行预冻和冷冻干燥，得到未改性鹿皮明胶冻干样品。",
    ),
    Replacement(
        "2.2.1.2",
        102,
        "热处理对照组（G-HT 组）在明胶完全溶解后",
        "热处理对照组（G-HT 组）在明胶完全溶解后，将体系 pH 调至 7.5，于 50 ℃ 水浴中保温 1 h，随后在 100 ℃ 水浴中处理 10 min。处理结束后，将样品液转入培养皿中，并按上述条件进行预冻和冷冻干燥。该组不添加 TGase，用作酶处理过程的热处理对照。",
    ),
    Replacement(
        "2.2.1.3",
        104,
        "二醛淀粉改性组包括 A1 组和 A2 组",
        "二醛淀粉改性组包括 A1 组和 A2 组，分别加入二醛淀粉 10 mg 和 20 mg。二醛淀粉先用少量温热去离子水分散后加入明胶溶液中，混匀后将体系 pH 调至 7.5，并以去离子水定容至 3.30 mL。随后于 37 ℃ 水浴中反应 2 h。反应结束后，将样品液转入培养皿中，并按上述条件进行预冻和冷冻干燥，得到二醛淀粉改性明胶冻干样品。",
    ),
    Replacement(
        "2.2.1.4",
        106,
        "谷氨酰胺转氨酶改性组包括 B1 组和 B2 组。",
        "谷氨酰胺转氨酶改性组包括 B1 组和 B2 组。TGase 储备液现配现用：准确称取 16 mg TGase，以冷去离子水溶解并定容至 1.00 mL，配制成质量浓度为 16 mg/mL 的储备液。明胶完全溶解后，先将体系 pH 调至 7.5，再分别加入 0.375 mL 和 0.625 mL TGase 储备液，对应 TGase 添加量分别为 6 mg 和 10 mg。混匀后于 50 ℃ 水浴中反应 1 h，随后在 100 ℃ 水浴中处理 10 min 以终止酶反应。最后将样品液转入培养皿中，并按上述条件进行预冻和冷冻干燥，得到 TGase 改性明胶冻干样品。",
    ),
    Replacement(
        "2.3.2-1",
        108,
        "溶胀率的测定用于评价不同改性条件下鹿皮明胶冻干样品对水分的吸收能力",
        "溶胀率测定用于评价不同改性条件下鹿皮明胶冻干样品对水分的吸收能力及其网络结构稳定性，是筛选较优改性条件的重要依据之一。该方法参考明胶基膜和水凝胶材料常用的重量法，并略作修改。",
    ),
    Replacement(
        "2.3.2-2",
        109,
        "将冻干后的凝胶样品切割成大小一致的试样",
        "将冻干后的凝胶样品切割成大小一致的试样，准确称取其初始干质量，记为 。将样品置于盛有 15 mL PBS 缓冲液的容器中，在 ℃ 条件下静置浸泡，分别于 0.5、1、2、4、8 和 24 h 取出样品。用滤纸轻轻吸去表面自由水后立即称重，记为 。每组设置 3 个平行样。",
    ),
    Replacement(
        "2.3.3-1",
        116,
        "水中溶失率测定用于表征不同改性条件下鹿皮明胶冻干样品在水介质中的质量损失情况",
        "水中溶失率测定用于表征不同改性条件下鹿皮明胶冻干样品在水介质中的质量损失情况，从而反映其耐水稳定性及交联程度。该指标与溶胀性能结合，可用于比较不同改性处理对鹿皮明胶结构稳定性的影响，也是确定较优改性条件的重要依据。该方法参考明胶膜和蛋白基材料水溶性或质量损失的常用测定方法，并略作修改。",
    ),
    Replacement(
        "2.3.3-2",
        117,
        "准确称取冻干凝胶样品的初始干质量",
        "准确称取冻干凝胶样品的初始干质量，记为 。将样品置于 15 mL PBS 缓冲液中，在 ℃ 条件下浸泡 24 h。浸泡结束后，取出样品并收集未溶解残余物，烘干至恒重，记其残余干质量为 。每组设置 3 个平行样。",
    ),
    Replacement(
        "2.3.3-4",
        123,
        "根据改性条件筛选试验中溶胀性能和溶失性能的测定结果",
        "根据改性条件筛选试验中溶胀性能和溶失性能的测定结果，分别筛选出 TG 酶改性和 DAS 改性交联的较优处理条件，并用于后续正式实验。",
    ),
    Replacement(
        "2.3.4-1",
        125,
        "在改性条件筛选试验基础上，正式实验共设 4 组",
        "在改性条件筛选试验基础上，正式实验共设 4 组，分别为原始鹿皮明胶组（DSG）、原始猪皮明胶组（PSG）、DAS 改性鹿皮明胶组（DAS-DSG）和 TG 酶改性鹿皮明胶组（TG-DSG），每组设 3 个独立平行，共计 12 个样品。其中，DAS-DSG 组采用筛选得到的较优 DAS 改性条件，TG-DAS组采用筛选得到的较优 TG 酶改性条件；G2 组作为阳性对照，用于比较鹿皮明胶经改性后与常规动物源明胶之间的性能差异。各组明胶终浓度均为 6.67%（w/v），最终体积统一为 15 mL。",
    ),
    Replacement(
        "2.3.4-2",
        126,
        "具体制备方法如下：准确称取明胶样品 1.00 g 于 50 mL 离心管中",
        "具体制备方法如下：准确称取明胶样品 1.00 g 于 50 mL 离心管中，加入去离子水 13 mL，置于 50 ℃ 恒温水浴中加热并间歇振荡。待明胶完全溶解后取出，必要时静置脱泡，并降温至约 40 ℃ 备用。DAS 改性组所用 DAS 母液按热母液预溶方案现配现用。准确称取 DAS 0.30 g 于 50 mL 离心管中，加入去离子水至 6 mL，充分润湿粉末后涡旋混匀，以避免形成干芯团块。将离心管置于 80～90 ℃ 热水浴中，间歇混匀，直至形成均一糊状或均一分散液。该体系不要求完全透明，但应避免明显硬颗粒残留。冷却至 40～50 ℃ 后备用。所得 DAS 母液浓度为 5%（w/v），供 3 个平行样使用。",
    ),
    Replacement(
        "2.3.4-3",
        127,
        "加入改性剂或空白对照液时",
        "加入改性剂或空白对照液时，G3 组向已溶解的鹿皮明胶液中加入 2 mL 5% DAS 母液，即每个样品实际加入 DAS 100 mg，轻柔混匀 2～3 min；G1 组和 G2 组加入 2 mL 空白对照液，并以相同方式轻柔混匀 2～3 min。G4 组则在明胶溶液中加入按 5 U/g 明胶计的 TGase 溶液，即每个样品加入 5 U TGase。该溶液现配现用，以冷去离子水溶解并定容至约 2 mL。混匀后置于 50 ℃ 恒温水浴中反应 1 h，反应结束后迅速转移至 100 ℃ 水浴中保持 10 min，以灭活酶活性，再取出冷却至约 40 ℃。G3 组在加入 DAS 母液后，于 37 ℃ 条件下预反应 1～2 h；若体系黏度上升过快，可酌情缩短至 30～60 min。G1 组和 G2 组不进行交联反应，直接进入下一步操作。",
    ),
    Replacement(
        "2.3.4-4",
        128,
        "反应完成后，将各组样液倒入对应编号的培养皿中",
        "反应完成后，将各组样液倒入对应编号的培养皿中，轻轻晃平液面并盖好皿盖，置于 4 ℃ 冰箱中静置 12～16 h 使其成型。成型后以去离子水洗涤 3 次，每次加入 10～15 mL 去离子水，轻摇 5 min 后倒去洗液，以去除未反应的 DAS 或 TGase 残留。洗涤完成后，将样品置于 −80 ℃ 超低温冰箱中预冻至少 4 h，随后转入冷冻干燥机中冻干。冷阱温度约为 −50 ℃，真空度小于 10 Pa，冻干时间为 48 h 或至样品质量基本恒定。冻干后取出样品，记录其颜色、完整性和脆性，研磨成粉末，密封后于 −20 ℃ 保存备用。",
    ),
    Replacement(
        "2.3.5-1",
        130,
        "持水率（water holding capacity，WHC）的测定参考相关文献方法并略作修改。",
        "持水率（water holding capacity，WHC）的测定参考相关文献方法并略作修改。准确称取冻干明胶粉末约 0.50 g，精确至 0.01 g，记为 ，置于已知质量的 50 mL 离心管中，离心管质量记为 。向离心管中加入 10 mL 去离子水，涡旋振荡 1 min，使样品充分分散，并于室温（25 ℃）条件下静置 30 min。随后以 3000 r/min 离心 20 min，小心倾去上清液。将离心管倒置于滤纸上沥干 5 min 后，称量离心管及沉淀总质量，记为 。各组样品平行测定 3 次，结果以平均值 ± 标准差表示。",
    ),
    Replacement(
        "2.3.6-1",
        137,
        "持油率（oil holding capacity，OHC）的测定参考相关文献方法并略作修改。",
        "持油率（oil holding capacity，OHC）的测定参考相关文献方法并略作修改。准确称取冻干明胶粉末约 0.50 g，精确至 0.01 g，记为 ，置于已知质量的 50 mL 离心管中，离心管质量记为 。向其中加入 10 mL 大豆油，涡旋振荡 1 min，使样品充分分散，并于室温（25 ℃）下静置 30 min。随后以 3000 r/min 离心 20 min，小心倾去上层油液。将离心管倒置于滤纸上沥干 5 min 后，称取离心管及含油沉淀总质量，记为 。各组样品平行测定 3 次，结果以平均值 ± 标准差表示。",
    ),
    Replacement(
        "2.3.7-1",
        144,
        "乳化活性指数（emulsifying activity index，EAI）和乳化稳定性指数",
        "乳化活性指数（emulsifying activity index，EAI）和乳化稳定性指数（emulsifying stability index，ESI）的测定参考 Pearce 和 Kinsella 的比浊法，并略作修改。准确称取冻干明胶粉末，以去离子水配制成浓度为 10 mg/mL 的明胶溶液，于 50 ℃ 水浴中充分溶解后冷却至室温。取明胶溶液 15 mL 与大豆油 5 mL 置于 50 mL 烧杯中混合，再以高速分散均质机在 10000 r/min 条件下均质 1 min，制备乳状液。",
    ),
    Replacement(
        "2.3.7-2",
        145,
        "均质结束后，立即从乳状液底部吸取 50 μL 样液",
        "均质结束后，立即从乳状液底部吸取 50 μL 样液，加入 5 mL 0.1%（w/v）SDS 溶液中，颠倒混匀。以 0.1% SDS 溶液为空白，在 500 nm 波长下测定吸光度，记为 。将乳状液静置 10 min 后，采用相同方法再次取样、稀释并测定吸光度，记为 。各组样品均平行测定 3 次，结果以平均值 ± 标准差表示。",
    ),
    Replacement(
        "2.3.8-1",
        154,
        "准确称取冻干明胶粉末，以去离子水配制成浓度为 1 mg/mL 的明胶溶液",
        "准确称取冻干明胶粉末，以去离子水配制成浓度为 1 mg/mL 的明胶溶液，于 50 ℃ 水浴中充分溶解后冷却至室温。以去离子水为空白参比，采用 1 cm 石英比色皿，在紫外-可见分光光度计上于 200～400 nm 波长范围内进行全波长扫描，扫描间隔为 1 nm。记录各组样品的紫外吸收光谱曲线，并比较不同处理组在特征吸收峰位置及峰强度上的差异，以分析不同改性方式对明胶分子构象和微观结构的影响。每组样品平行扫描 3 次。",
    ),
    Replacement(
        "2.3.9-1",
        156,
        "傅里叶变换红外光谱（FTIR）测定采用 KBr 压片法。",
        "傅里叶变换红外光谱（FTIR）测定采用 KBr 压片法。取适量冻干明胶粉末与干燥 KBr 按质量比约 1∶100 混合，于玛瑙研钵中充分研磨至均匀细粉，再用压片模具压制成透明薄片。以纯 KBr 压片为背景，在傅里叶变换红外光谱仪上进行测定。扫描范围为 4000～400 cm⁻¹，分辨率为 4 cm⁻¹，扫描累加次数为 32 次。",
    ),
    Replacement(
        "2.3.9-2",
        157,
        "记录各组样品的红外吸收光谱",
        "记录各组样品的红外吸收光谱，重点分析酰胺 A 带（约 3300 cm⁻¹）、酰胺 I 带（约 1650 cm⁻¹）、酰胺 II 带（约 1540 cm⁻¹）和酰胺 III 带（约 1240 cm⁻¹）等特征吸收峰的位置及强度变化。对于 DAS 改性样品，重点关注约 1630 cm⁻¹ 附近是否出现与亚胺键（C=N）相关的特征吸收峰，以辅助判断 Schiff 碱交联反应是否发生。每组样品平行测定 3 次。",
    ),
    Replacement(
        "2.4-1",
        160,
        "所有实验均独立重复 3 次，数据以平均值 ± 标准差（mean ± SD）表示。",
        "所有实验均独立重复 3 次，数据以平均值 ± 标准差（mean ± SD）表示。采用 GraphPad Prism 10.2.3（GraphPad Software, Boston, MA, USA）进行单因素方差分析（one-way ANOVA），组间均值的多重比较采用 Tukey HSD 检验，显著性水平设定为 α = 0.05。图表绘制采用 GraphPad Prism 10.2.3（GraphPad Software, Boston, MA, USA）完成。",
    ),
    Replacement(
        "3.1.1",
        167,
        "不同改性条件筛选组样品的溶胀率结果如图3.1 A、B 所示。",
        "不同改性条件筛选组样品的溶胀率结果如图3.1 A、B 所示。各组样品的溶胀率均随浸泡时间延长而升高，并多在 8 h 左右达到较高水平，至 24 h 略有回落，提示样品在吸水膨胀后伴随一定的网络松弛及部分可溶组分迁移。Raw 组与 HeatCtrl 组在整个浸泡过程中始终保持较高溶胀率，8 h 时分别达到（6905.26±83.89）% 和（6849.42±65.19）%，24 h 时分别为（6244.85±167.67）% 和（6148.74±213.73）%。24 h 终点统计比较显示，Raw 组与 HeatCtrl 组的溶胀率最高，二者差异不显著（p>0.05），但均显著高于各交联处理组（p<0.05）。在交联处理组中，DAS-2 组数值最低；TGase-1 组显著高于 DAS-2 组和 DAS-1 组（p<0.05），但与 TGase-2 组差异不显著（p>0.05）；DAS-1 组与 TGase-2 组之间差异也不显著（p>0.05）。这一结果表明，DAS 与 TGase 交联均能有效抑制鹿皮明胶冻干凝胶的过度吸水膨胀，其中 DAS 处理的整体抑制作用更强。该趋势与已有研究报道的总体规律一致，即 DAS-gelatin 体系可通过亚胺键和氢键协同形成更致密的交联网络，而 TGase 交联也有助于提高 gelatin 网络的稳定性并降低其水敏感性。因此，本研究中交联组 24 h 溶胀率显著低于未改性组具有一定的结构基础。",
    ),
    Replacement(
        "3.1.2",
        169,
        "各组样品 24 h 溶失率结果如图3.1 C 所示。",
        "各组样品 24 h 溶失率结果如图3.1 C 所示。Raw 组和 HeatCtrl 组溶失率最高，分别为（29.46±1.47）% 和（32.45±2.61）%，二者差异不显著（p>0.05），但均显著高于各交联处理组（p<0.05）。这一结果表明，未改性样品及单纯热处理样品在水介质中更易发生质量损失。经交联处理后，样品溶失率整体降至 9.72%～14.82%。其中，DAS-2 组数值最低，为（9.72±1.42）%；TGase-1 组为（14.82±1.18）%，显著高于 DAS-2 组（p<0.05）；DAS-1 组（11.55±1.29）% 与 TGase-2 组（13.60±1.20）% 处于中间水平，与 DAS-2 组或 TGase-1 组之间差异均不显著（p>0.05）。结合 24 h 溶胀率结果可见，交联处理同时降低了样品的吸水膨胀和水中质量损失，说明两种改性方式均提高了网络完整性和水中稳定性。其中，DAS 处理在数值上表现出更低的终点溶失率，提示其对限制链段溶出和维持网络完整性可能更为有利。该趋势与已有文献关于 DAS 交联可提高 gelatin 体系 swelling stability，以及 MTGase 交联可降低 gelatin 水溶性并增强网络稳定性的报道一致，也为后续正式实验条件的确定提供了依据。",
    ),
    Replacement(
        "3.2.1",
        175,
        "四组明胶样品的凝胶强度结果如图3.2 所示。",
        "四组明胶样品的凝胶强度结果如图3.2 所示。DSG 的凝胶强度最低，为（187.37±5.73）g，显著低于 PSG（218.53±5.01）g，提示在相同制胶条件下，未经改性的鹿皮明胶在凝胶网络完整性和抗形变能力方面弱于猪皮明胶。经改性后，鹿皮明胶的凝胶强度均显著升高。其中，DAS-DSG 最高，为（276.40±7.56）g，显著高于 TG-DSG（251.80±4.81）g、PSG 和 DSG（p<0.05）；TG-DSG 也显著高于 PSG 和 DSG（p<0.05）。这一趋势与已有研究中 DAS 与明胶之间通过亚胺键和氢键协同构建更强网络，以及 TGase 交联可提高明胶材料机械性能和网络致密性的报道一致。与 TG-DSG 相比，DAS-DSG 的提升幅度更大，这表明在本实验条件下，DAS 的多点交联作用可能更有利于增强凝胶网络。需要指出的是，凝胶强度的绝对值还受明胶来源、Bloom 等级、固形物浓度及冷却成熟条件等因素影响，因此与其他研究结果不宜仅依据数值大小进行简单横向比较；但就组间变化趋势而言，本研究结果能够较为稳定地反映改性处理对鹿皮明胶凝胶性能的增强效应。综合来看，两种改性方式均可在不同程度上弥补鹿皮明胶天然凝胶性偏弱的不足，其中 DAS-DSG 表现出更优的凝胶强度，提示其在凝胶型食品或功能性胶体体系中具有较好的应用前景。",
    ),
    Replacement(
        "3.2.2",
        180,
        "四组明胶样品的乳化活性指数（EAI）结果如图3.3 A 所示。",
        "四组明胶样品的乳化活性指数（EAI）结果如图3.3 A 所示。DAS-DSG 的 EAI 最高，为（33.51±0.96）m²/g，显著高于其余 3 组（p<0.05）；TG-DSG 次之，为（32.46±0.87）m²/g；PSG 为（28.62±0.91）m²/g；DSG 最低，为（24.32±0.73）m²/g。该结果表明，DAS 与 TGase 改性均可改善鹿皮明胶的界面活性，但提升幅度并不完全相同。DAS-DSG 具有最高 EAI，提示在本实验体系中，DAS 交联可能更有利于促进分子链构象重排，并增强界面活性基团在油水界面的快速定向吸附能力，从而提高单位质量蛋白的界面覆盖能力。总体来看，改性处理均有助于提升鹿皮明胶在乳化形成初期的界面吸附性能，其中 DAS 改性的促进作用更为突出。",
    ),
    Replacement(
        "3.2.3",
        182,
        "四组明胶样品的乳化稳定性指数（ESI）结果如图3.3 B 所示。",
        "四组明胶样品的乳化稳定性指数（ESI）结果如图3.3 B 所示。TG-DSG 的 ESI 最高，为（29.47±0.56）min；DAS-DSG 次之，为（26.98±0.64）min；PSG 为（21.97±0.65）min；DSG 最低，为（18.40±0.72）min。该趋势与已有研究中 TG 交联常可增强明胶乳液稳定性、而乳化活性存在最佳交联区间的报道一致。由此推断，较为致密的酶促交联网络可能更有利于形成机械强度较高且抗聚并能力较强的界面膜。相比之下，DAS-DSG 在 EAI 上占优，而在 ESI 上略低于 TG-DSG，提示 DAS 改性更可能促进初始吸附，而 TGase 改性则更有利于界面膜后续稳定性的维持。需要强调的是，EAI 和 ESI 反映的是界面行为的综合结果，具体机制仍需结合结构表征与流变证据进行综合判断，因此上述解释应理解为基于现有数据的合理推断。",
    ),
    Replacement(
        "3.2.4",
        187,
        "四组明胶的持水性（WHC）结果如图3.4 A 所示。",
        "四组明胶的持水性（WHC）结果如图3.4 A 所示。DAS-DSG 的 WHC 最高，为（7.46±0.23）g/g；TG-DSG 次之，为（7.29±0.17）g/g，二者均显著高于 PSG（6.34±0.20）g/g 和 DSG（5.61±0.17）g/g（p<0.05），而 DAS-DSG 与 TG-DSG 之间差异不显著（p>0.05）。该结果表明，两种改性方式均提高了鹿皮明胶对水分的保持能力。这提示交联处理在增强网络强度的同时，可能也调节了材料内部孔隙结构及亲水基团的空间分布。该趋势与已有研究中 DAS 或 TG 交联可增强明胶材料水稳定性和网络致密性的报道基本一致。尽管交联程度升高并不必然导致 WHC 增加，但在本研究体系下，改性鹿皮明胶表现出更好的保水性能，提示其在需要较高保水性的食品体系中具有应用潜力。",
    ),
    Replacement(
        "3.2.5",
        189,
        "四组明胶的持油性（OHC）结果如图3.4 B 所示。",
        "四组明胶的持油性（OHC）结果如图3.4 B 所示。DAS-DSG（4.13±0.10）g/g 与 TG-DSG（4.00±0.09）g/g 均显著高于 PSG（3.72±0.11）g/g 和 DSG（3.14±0.10）g/g（p<0.05）。总体来看，两种改性方式均提高了鹿皮明胶对油脂的保持能力，提示交联处理在增强网络完整性的同时，可能也有助于形成更有利于油脂滞留的微观结构。需要指出的是，OHC 受材料孔隙结构、链段柔顺性及非极性基团暴露程度等多因素共同影响，因此本研究结果更适合理解为当前配方与交联水平下形成了较为有利的持油结构，而不宜简单外推至所有改性明胶体系。尽管如此，改性鹿皮明胶在 OHC 上均优于 PSG，仍提示其在需要保脂能力的食品体系中具有作为替代胶源的可行性。",
    ),
    Replacement(
        "3.3.1",
        196,
        "四组明胶的紫外吸收光谱如图3.5 所示。",
        "四组明胶的紫外吸收光谱如图3.5 所示。各组样品均在约 230 nm 处出现强吸收峰，对应蛋白质肽键相关吸收；在约 280 nm 处出现次级吸收肩峰，主要与芳香族氨基酸残基的微环境有关。在 230 nm 和 280 nm 处，各组吸光度均呈 DAS-DSG > TG-DSG > PSG > DSG 的趋势，提示两种改性处理均改变了多肽链发色团周围的微环境，并可能提高了部分肽键及芳香族残基的可检测性。已有研究表明，TG 交联和醛基型交联均可引起 gelatin 分子构象重排，相关变化可在 UV–Vis 光谱中表现为特征吸收强度改变；本研究结果与这一总体规律相符。需要指出的是，UV 吸收增强更适宜解释为分子构象与微环境发生变化，而不能仅凭 230 nm 或 280 nm 处吸光度升高就直接判定蛋白质三级结构“展开”或某一种二级结构比例必然升高。因此，从本研究数据出发，更为稳妥的表述是：DAS-DSG 和 TG-DSG 相较于原始明胶发生了更明显的构象重排，其中 DAS-DSG 的变化幅度最大；而 DSG 吸光度整体偏低，则提示其分子链在当前测试条件下对相关发色团的响应相对较弱。",
    ),
    Replacement(
        "3.3.2",
        202,
        "四组明胶的 FTIR 光谱如图3.6 所示。",
        "四组明胶的 FTIR 光谱如图3.6 所示。各组均呈现明胶蛋白质的典型酰胺吸收带。与 DSG 相比，DAS-DSG 在 Amide A 区域的峰位由 3294 cm⁻¹ 移动至 3287 cm⁻¹，TG-DSG 的峰位（3290 cm⁻¹）则介于两者之间。通常而言，Amide A 向低波数方向移动可提示氢键作用增强，因此本结果支持改性处理后分子间相互作用增强的判断，其中 DAS-DSG 的变化更为明显。这与已有文献中 DAS 与 gelatin 之间可同时形成亚胺键和氢键、TG 交联可促使 gelatin 网络更致密的报道相一致。与此同时，Amide I 和 Amide II 区域峰位及强度的变化表明，交联处理改变了肽链周围的化学环境和分子有序程度，提示蛋白质二级结构发生了一定程度的重排。需要注意的是，常规 FTIR 峰位变化能够反映结构环境改变，但若未进行酰胺 I 带分峰拟合或二维相关分析，则不宜直接定量推断 β-折叠、α-螺旋等具体二级结构组分的增减幅度。因此，本研究更适宜将 FTIR 结果表述为：DAS 和 TGase 均改变了鹿皮明胶分子链的相互作用方式和局部构象，其中 DAS-DSG 的结构响应更强，这为其在凝胶强度、乳化特性及持水持油性能上的改善提供了结构层面的支持。",
    ),
    Replacement(
        "4.1-1",
        205,
        "本研究以鹿皮明胶为原料，分别采用二醛淀粉",
        "本研究以鹿皮明胶为原料，分别采用二醛淀粉（DAS）和谷氨酰胺转氨酶（TGase）两种方式对其进行改性处理，并以未改性鹿皮明胶（DSG）和猪皮明胶（PSG）为对照，系统比较了不同改性处理对鹿皮明胶功能特性和结构特性的影响。结果表明，两种改性方式均能在不同程度上改善鹿皮明胶的综合性能，但二者在作用方式和效果侧重上存在明显差异。整体结果与已有文献报道的规律基本一致，同时也呈现出鹿皮明胶原料本身的一些特点。",
    ),
    Replacement(
        "4.1-2",
        206,
        "在改性条件筛选阶段，溶胀率和溶失率结果共同表明",
        "在改性条件筛选阶段，溶胀率和溶失率结果共同表明，DAS 与 TGase 交联均可有效降低鹿皮明胶冻干凝胶的吸水膨胀程度和水介质中的质量损失，说明两种改性方式均能提高材料网络的水稳定性。其中，DAS 处理，尤其是高添加量组，在抑制溶胀率和溶失率方面整体优于 TGase 处理。这提示 DAS 与明胶分子中氨基之间形成的亚胺键（Schiff 碱）及其与氢键的协同作用，可能有助于在分子链间构建更致密的交联网络。而 TGase 则通过催化谷氨酰胺残基与赖氨酸残基之间形成酰胺键，建立相对温和的酶促交联，其网络密度提升程度相对有限。不过，该结果与 Xu 等人关于 TGase 交联可降低明胶溶解性并增强网络稳定性的报道趋势一致。上述筛选结果为正式实验中改性条件的确定提供了依据。",
    ),
    Replacement(
        "4.1-3",
        207,
        "在功能特性方面，凝胶强度结果显示",
        "在功能特性方面，凝胶强度结果显示，DSG 的凝胶强度显著低于 PSG，表明在相同制备条件下，鹿皮明胶的凝胶网络形成能力相对较弱。这可能与鹿皮胶原的氨基酸组成，如脯氨酸和羟脯氨酸含量，以及链段特征有关。两种改性处理均显著提高了凝胶强度，其中 DAS-DSG 的提升幅度最大，且超过 PSG，这一结果与其可能形成较致密多点交联网络的机制相符；TG-DSG 的凝胶强度也显著高于 PSG 和 DSG，说明酶促交联同样能够有效弥补鹿皮明胶天然凝胶性偏弱的不足。乳化特性方面，DAS-DSG 的乳化活性指数（EAI）最高，提示 DAS 改性可能通过链段构象重排促进界面活性基团暴露，从而提高初始界面吸附能力；而 TG-DSG 的乳化稳定性指数（ESI）最高，说明酶促交联形成的界面膜可能具有更高的机械强度和更强的抗聚并能力，更有利于维持乳液稳定性。这一 EAI 与 ESI 的差异化趋势提示，DAS 改性更偏向于促进乳化初始阶段的界面吸附，而 TGase 改性则更有利于后续乳化稳定性的维持，与已有研究中 TG 交联促进界面膜稳定性的报道基本一致。在持水性和持油性方面，两种改性明胶均优于 DSG 和 PSG，说明交联处理不仅增强了网络致密性，也可能改善了材料内部孔隙结构及亲水/疏水基团的空间可及性，从而有助于水分和油脂的保留。这提示改性鹿皮明胶在需要较高保水和保脂能力的食品体系中具有较好的应用适应性。",
    ),
    Replacement(
        "4.1-4",
        208,
        "在结构特性方面，紫外吸收光谱和 FTIR 结果共同支持了功能特性数据所反映的改性效果。",
        "在结构特性方面，紫外吸收光谱和 FTIR 结果共同支持了功能特性数据所反映的改性效果。UV 光谱中，DAS-DSG 和 TG-DSG 在 230 nm 和 280 nm 处的吸光度均高于 DSG 和 PSG，提示两种改性处理均引起了明胶分子构象重排，并改变了肽键及芳香族氨基酸残基所处的微环境，其中 DAS-DSG 的变化幅度更大。FTIR 光谱中，Amide A 峰向低波数方向偏移的程度以 DAS-DSG 最为明显，这支持了 DAS 改性后分子间氢键增强的判断；Amide I 和 Amide II 区域峰位及强度的变化则提示交联处理改变了肽链二级结构的局部有序程度。需要指出的是，本研究中的结构表征仅基于常规 UV 扫描和 FTIR 测定，未进一步开展 SDS-PAGE 分子量分析、DSC 热分析或流变测定。因此，对结构变化的解读目前仍限于峰位和吸光度的定性比较，后续仍需借助更精细的表征手段加以深入阐释。",
    ),
    Replacement(
        "4.1-5",
        209,
        "综合以上分析，本研究结果表明",
        "综合以上分析，本研究结果表明，DAS 和 TGase 两种改性方式均可有效调控鹿皮明胶的结构与功能，且各有侧重：DAS 改性在凝胶强度、乳化活性、持水性和持油性方面表现更为突出，而 TGase 改性则在乳化稳定性方面具有优势。从食品应用角度看，DAS-DSG 更适合应用于对凝胶强度和乳化形成能力要求较高的体系，而 TG-DSG 则在需要较高乳液稳定性的场景中具有一定优势。当然，本研究仍存在若干局限：其一，仅设置了两种改性方式的单一剂量正式实验组，未系统考察剂量-效应关系；其二，缺乏 SDS-PAGE、DSC 和流变等更深入的结构与热力学表征；其三，鹿皮明胶本身的来源特征，如脯氨酸和羟脯氨酸含量、分子量分布等，尚未进行详细分析。这些问题均有待后续研究进一步完善。",
    ),
    Replacement(
        "4.2-1",
        211,
        "本研究初步揭示了 DAS 和 TGase 两种改性方式",
        "本研究初步揭示了 DAS 和 TGase 两种改性方式对鹿皮明胶结构与功能特性的调控规律，验证了鹿皮作为非传统明胶原料的可改性潜力。然而，现有研究仍处于探索阶段，后续工作可从以下几个方面进一步深入。",
    ),
    Replacement(
        "4.2-2",
        212,
        "第一，深化鹿皮明胶基础特性的系统表征。",
        "第一，深化鹿皮明胶基础特性的系统表征。本研究中，DSG 与 PSG 在凝胶强度等性能上存在明显差异，但鹿皮明胶的分子量分布、氨基酸组成，尤其是脯氨酸和羟脯氨酸含量，以及胶原来源特征尚未得到系统表征。未来研究应首先通过 SDS-PAGE、氨基酸组成分析及凝胶色谱等手段，对鹿皮明胶的基础理化参数进行详细描述，为改性机制的深入阐释提供结构依据，也有助于与其他来源明胶进行更系统的比较。",
    ),
    Replacement(
        "4.2-3",
        213,
        "第二，优化改性条件并建立剂量-效应关系。",
        "第二，优化改性条件并建立剂量-效应关系。本研究正式实验仅采用筛选得到的单一改性剂量，未能系统反映改性剂用量对各功能指标的影响规律。后续研究可通过设计多梯度实验或响应面优化方案，系统考察 DAS 添加量和 TGase 活性对凝胶强度、乳化特性及持水持油率等指标的影响，从而建立更为可靠的剂量-效应模型，为实际应用中改性条件的精准调控提供依据。",
    ),
    Replacement(
        "4.2-4",
        214,
        "第三，引入多维结构表征手段，深化改性机制研究。",
        "第三，引入多维结构表征手段，深化改性机制研究。本研究的结构表征主要依赖 UV-Vis 光谱和 FTIR 测定，仅能提供较为宏观的分子构象和官能团变化信息。后续研究应进一步引入差示扫描量热法（DSC）分析热稳定性变化，采用流变仪测定凝胶网络的黏弹性参数，并借助扫描电子显微镜（SEM）观察冻干凝胶的微观孔隙结构，以从热力学、流变学和形貌学多个维度深入理解 DAS 和 TGase 改性对鹿皮明胶网络结构的调控机制。",
    ),
    Replacement(
        "4.2-5",
        215,
        "第四，探索复合改性及多功能应用潜力。",
        "第四，探索复合改性及多功能应用潜力。目前研究仅对 DAS 和 TGase 两种方式进行独立处理，而两者在改性机制和功能侧重上存在一定互补性——DAS 偏向于提高凝胶强度和乳化活性，TGase 则更有利于维持乳化稳定性。将两者进行合理组合的复合改性策略，有望实现对鹿皮明胶综合性能的协同提升。此外，后续研究还可进一步探索改性鹿皮明胶在可食用膜、功能性凝胶食品及蛋白质基乳化体系中的实际应用效果，为其产业化开发提供理论支撑。",
    ),
    Replacement(
        "4.2-6",
        216,
        "第五，拓展鹿皮明胶的原料来源与提取工艺研究。",
        "第五，拓展鹿皮明胶的原料来源与提取工艺研究。本研究所用鹿皮明胶为商品化产品，其原料来源和制备工艺参数尚不明确。未来可结合自主提取工艺，系统比较不同预处理方式（酸法、碱法、酶辅助法）对鹿皮明胶得率及基础性质的影响，进一步明确制备条件对改性效果的潜在作用，为建立完整的鹿皮明胶“提取—改性—应用”技术体系提供基础。",
    ),
    Replacement(
        "4.2-7",
        217,
        "总体而言，鹿皮明胶作为一种来源于非传统动物副产物的天然高分子材料",
        "总体而言，鹿皮明胶作为一种来源于非传统动物副产物的天然高分子材料，兼具资源特殊性和改性可调控性，具有较好的开发应用潜力。随着分析手段的不断完善和改性研究的持续深入，其有望在功能食品、生物活性包装及蛋白质基功能材料等领域实现更广泛的应用。",
    ),
]

MATH_REPLACEMENTS = [
    Replacement("2.3.2-2", 109, "将冻干后的凝胶样品切割成大小一致的试样", ""),
    Replacement("2.3.3-2", 117, "准确称取冻干凝胶样品的初始干质量", ""),
    Replacement("2.3.5-1", 130, "持水率（water holding capacity，WHC）的测定参考相关文献方法并略作修改。", ""),
    Replacement("2.3.6-1", 137, "持油率（oil holding capacity，OHC）的测定参考相关文献方法并略作修改。", ""),
    Replacement("2.3.7-2", 145, "均质结束后，立即从乳状液底部吸取 50 μL 样液", ""),
]

MATH_RUN_TEXTS = {
    109: [
        "将冻干后的凝胶样品切割成大小一致的试样，准确称取其初始干质量，记为 ",
        "。将样品置于盛有 15 mL PBS 缓冲液的容器中，在 ",
        "℃ 条件下静置浸泡，分别于 0.5、1、2、4、8 和 24 h 取出样品。用滤纸轻轻吸去表面自由水后立即称重，记为 ",
        "。每组设置 3 个平行样。",
    ],
    117: [
        "准确称取冻干凝胶样品的初始干质量，记为 ",
        "。将样品置于 15 mL PBS 缓冲液中，在 ",
        "℃ 条件下浸泡 24 h。浸泡结束后，取出样品并收集未溶解残余物，烘干至恒重，记其残余干质量为 ",
        "。每组设置 3 个平行样。",
    ],
    130: [
        "持水率（water holding capacity，WHC）的测定参考相关文献方法并略作修改。准确称取冻干明胶粉末约 0.50 g，精确至 0.01 g，记为 ",
        "，置于已知质量的 50 mL 离心管中，离心管质量记为 ",
        "。向离心管中加入 10 mL 去离子水，涡旋振荡 1 min，使样品充分分散，并于室温（25 ℃）条件下静置 30 min。随后以 3000 r/min 离心 20 min，小心倾去上清液。将离心管倒置于滤纸上沥干 5 min 后，称量离心管及沉淀总质量，记为 ",
        "。各组样品平行测定 3 次，结果以平均值 ± 标准差表示。",
    ],
    137: [
        "持油率（oil holding capacity，OHC）的测定参考相关文献方法并略作修改。准确称取冻干明胶粉末约 0.50 g，精确至 0.01 g，记为 ",
        "，置于已知质量的 50 mL 离心管中，离心管质量记为 ",
        "。向其中加入 10 mL 大豆油，涡旋振荡 1 min，使样品充分分散，并于室温（25 ℃）下静置 30 min。随后以 3000 r/min 离心 20 min，小心倾去上层油液。将离心管倒置于滤纸上沥干 5 min 后，称取离心管及含油沉淀总质量，记为 ",
        "。各组样品平行测定 3 次，结果以平均值 ± 标准差表示。",
    ],
    145: [
        "均质结束后，立即从乳状液底部吸取 50 μL 样液，加入 5 mL 0.1%（w/v）SDS 溶液中，颠倒混匀。以 0.1% SDS 溶液为空白，在 500 nm 波长下测定吸光度，记为 ",
        "。将乳状液静置 10 min 后，采用相同方法再次取样、稀释并测定吸光度，记为 ",
        "。各组样品均平行测定 3 次，结果以平均值 ± 标准差表示。",
    ],
}


def apply_replacements(document_root: ET.Element):
    paragraphs = list(document_root.findall(".//w:p", NSMAP))
    results = []
    missing = []

    for item in REPLACEMENTS:
        target = paragraphs[item.index] if item.index < len(paragraphs) else None
        matched = False

        if target is not None and not paragraph_has_math(target):
            current_text = paragraph_text(target)
            if normalize_text(current_text).startswith(normalize_text(item.locator)):
                matched = True
        if not matched:
            for idx, candidate in enumerate(paragraphs):
                if paragraph_has_math(candidate):
                    continue
                current_text = paragraph_text(candidate)
                if normalize_text(current_text).startswith(normalize_text(item.locator)):
                    target = candidate
                    matched = True
                    item_index = idx
                    break
            if not matched:
                missing.append(item)
                continue
        else:
            item_index = item.index

        before = paragraph_text(target)
        changed = normalize_text(before) != normalize_text(item.replacement)
        rewrite_paragraph_text_preserve_runs(target, item.replacement)
        results.append(
            {
                "label": item.label,
                "index": item_index,
                "changed": changed,
                "before": before,
                "after": item.replacement,
            }
        )

    return results, missing


def apply_math_replacements(document_root: ET.Element):
    paragraphs = list(document_root.findall(".//w:p", NSMAP))
    results = []
    missing = []

    for item in MATH_REPLACEMENTS:
        target = paragraphs[item.index] if item.index < len(paragraphs) else None
        matched = False

        if target is not None:
            current_text = paragraph_text(target)
            if normalize_text(current_text).startswith(normalize_text(item.locator)):
                matched = True
                item_index = item.index
        if not matched:
            for idx, candidate in enumerate(paragraphs):
                current_text = paragraph_text(candidate)
                if normalize_text(current_text).startswith(normalize_text(item.locator)):
                    target = candidate
                    matched = True
                    item_index = idx
                    break
            if not matched:
                missing.append(item)
                continue

        before = paragraph_text(target)
        if not rewrite_paragraph_preserve_math_runs(target, MATH_RUN_TEXTS[item_index]):
            missing.append(item)
            continue
        after = paragraph_text(target)
        changed = normalize_text(before) != normalize_text(after)
        results.append(
            {
                "label": item.label,
                "index": item_index,
                "changed": changed,
                "before": before,
                "after": after,
            }
        )

    return results, missing


def build_log(applied, missing, input_path, output_path):
    changed = [item for item in applied if item["changed"]]
    already = [item for item in applied if not item["changed"]]

    lines = [
        "# Word 学术润色修改日志",
        "",
        f"- 输入文件：`{input_path}`",
        f"- 输出文件：`{output_path}`",
        "",
        "## 已自动修改",
        "- 中文摘要：按当前文件的 3 个摘要段落重写为同一版学术摘要内容。",
        "- 第1章：已按清单替换绪论、物理改性、复合改性、制备方法及研究目的和意义中的指定段落。",
        "- 第2章：已按清单规范方法学描述，保留公式对象、图表对象和原有段落结构。",
        "- 第3章：已按清单优化结果-解释逻辑链，并将机制说明统一为更审慎表述。",
        "- 第4章：已按清单润色结论与展望正文，不改标题结构。",
        f"- 实际命中段落：{len(applied)} 处，其中发生文本变化 {len(changed)} 处，已与目标一致 {len(already)} 处。",
        "",
        "## 未自动修改（需人工确认）",
        "1. 2.3.4 中出现 `TG-DAS组`，疑似应为 `TG-DSG组`；按要求仅保留并标记。",
        "2. 2.3.4 中 `G1/G2/G3/G4` 与 `DSG/PSG/DAS-DSG/TG-DSG` 两套命名体系并存；按要求未自动统一。",
        "3. 2.3.2、2.3.3 等公式说明处存在变量空缺显示；脚本未修改公式对象本身。",
        "4. 图3.3 图注写为 `Duncan 检验`，而 2.4 统计分析写为 `Tukey HSD 检验`；按要求未自动改动。",
        "5. 目录、页码、页眉页脚、图表、参考文献列表、英文摘要和英文关键词均未改动。",
        "",
        "## 段落命中明细",
    ]

    for item in changed:
        preview = item["after"][:60].replace("\n", " ")
        lines.append(f"- `{item['label']}`：段落索引 {item['index']}，已替换为 `{preview}...`")
    for item in already:
        lines.append(f"- `{item['label']}`：段落索引 {item['index']}，当前文本已与目标一致。")

    if missing:
        lines.extend(["", "## 未命中替换项"])
        for item in missing:
            lines.append(f"- `{item.label}`：未找到以 `{item.locator[:40]}...` 开头的正文段落。")

    return "\n".join(lines) + "\n"


def polish_docx(input_path: str, output_path: str, log_path: str):
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(input_path, "r") as source_zip:
            source_zip.extractall(temp_dir)

        document_path = os.path.join(temp_dir, "word", "document.xml")
        with open(document_path, "rb") as handle:
            document_root = ET.fromstring(handle.read())

        applied, missing = apply_replacements(document_root)
        math_applied, math_missing = apply_math_replacements(document_root)
        applied.extend(math_applied)
        missing.extend(math_missing)
        applied_labels = {item["label"] for item in applied}
        missing = [item for item in missing if item.label not in applied_labels]

        with open(document_path, "wb") as handle:
            handle.write(ET.tostring(document_root, encoding="utf-8", xml_declaration=True))

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target_zip:
            for root_dir, _, files in os.walk(temp_dir):
                for filename in files:
                    full_path = os.path.join(root_dir, filename)
                    rel_path = os.path.relpath(full_path, temp_dir)
                    target_zip.write(full_path, rel_path)

    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(build_log(applied, missing, input_path, output_path))

    return applied, missing


def main():
    parser = argparse.ArgumentParser(description="对学位论文 docx 执行安全段落级中文润色。")
    parser.add_argument("input", help="输入 docx 文件")
    parser.add_argument("--output", required=True, help="输出 docx 文件")
    parser.add_argument("--log", required=True, help="输出 markdown 日志")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
    applied, missing = polish_docx(args.input, args.output, args.log)
    print(f"applied={len(applied)} missing={len(missing)}")


if __name__ == "__main__":
    main()
