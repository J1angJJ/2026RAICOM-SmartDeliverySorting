# 场地先验地图

`field_map.json` 从比赛喷绘母版 `足式组-3x2.5m.tif` 的原始图层量取，统一使用
米制 `field` 坐标系：原点是喷绘布左下角，x 轴向右，y 轴向上，逆时针为正
偏航角。矩形 `bounds` 的顺序为 `[min_x, min_y, max_x, max_y]`。

当前地图记录：

- 三段循迹线的中心折线与线宽；
- A、B、C、D 四个放置圆的圆心和半径；
- 包裹抓取区的中心、尺寸和边界；
- 两个识别区的中心、尺寸和边界；
- 位于识别区正中心的两个 `0.3m x 0.3m x 0.3m` 箱体。

只有两个识别箱体属于已知静态障碍。地面印刷图案不是障碍，外围围挡位置尚未
确认，不能写进先验占据层。箱体朝向也暂不假定；正方形俯视占据不受朝向影响。

TIFF 的 8504x7087 像素画布直接对应 3.0x2.5m 成品尺寸，72 DPI 元数据不参与
换算。图层量取很精确，但喷绘裁切、铺设和箱体摆放仍有现场误差，正式比赛前应
测量若干控制点并更新 `uncertainty`。

Python 中读取地图：

```python
from xgo26.field_map import load_field_map

field_map = load_field_map()
box_1 = field_map.cube("recognition_cube_1")
target_a, target_a_radius = field_map.drop_target("A")
```

这份 JSON 是语义矢量真值源。以后若导航模块需要 2cm 或 5cm 栅格，应由它派生
占据层、循迹层和任务区域层，不要手工维护另一份坐标。
