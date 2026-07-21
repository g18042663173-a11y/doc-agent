# 帧头接口

下列结构定义用于帧级消息传输。

```c
typedef struct {
    uint16_t frame_id;
    uint8_t payload[32];
} FrameHeader;
```

字段定义见接口参数表。
