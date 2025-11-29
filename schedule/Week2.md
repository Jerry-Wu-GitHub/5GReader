# 第二周分工

## 插件关系图

```mermaid
graph LR
	classDef Plugin stroke:#6090b8,stroke-width:4px;

	subgraph 视图界面
		View[View: 多种视图界面]
		SelectAndDrag[Select&Drag: 选择框]
	end
	
	subgraph OCR
		OpticalCharacterRecognition[OCR: 从图像中识别文字]
	end
	
	subgraph AI
		AIConfigure[AIConfigure: 配置参数]
		Summary[Summary: 显示总结]
		MindMap[MindMap: 显示导图]
	end
	class 视图界面,OCR,AI Plugin
	
	subgraph "<code>pymupdf.Page</code>"
		rect(.rect)
        get_text(".get_text()")
        get_images(".get_images()")
        get_image_bbox(".get_image_bbox()")
	end
	
	subgraph "<code>ReaderAccess</code>"
		get_selected_text(".get_selected_text()")
		data(.data)
		get_AI_configuration(".get_AI_configuration()")
	end

	subgraph "<code>Tab</code>"
		zoom(.zoom)
		display_mode(.display_mode)
		doc(.doc)
		canvas(.canvas)
		page_no(.page_no)
		canvas_width(.canvas_width)
		canvas_height(.canvas_height)
		canvas_rect(.canvas_rect)
		visible_page_positions(.visible_page_positions)
        selectable_page_positions(.selectable_page_positions)
        coord2real(".coord2real()")
        render(".render()")
        
        visible_page_positions --> render
	end

	subgraph "<code>tkinter</code>"
		Event(Event)
		Tk(Tk)
	end

	zoom --> View
	display_mode --> View
	doc --> View
	canvas --> View
	rect --> View
	View -->|overload| canvas_width
	View -->|overload| canvas_height
	View -->|overload| canvas_rect
	View -->|overload| visible_page_positions
	View -->|overload| selectable_page_positions
	View -->|overload| coord2real

	selectable_page_positions --> SelectAndDrag
	get_text --> SelectAndDrag
	Event --> SelectAndDrag
	SelectAndDrag -->|bind| canvas
	SelectAndDrag -->|set| get_selected_text

	get_images --> OpticalCharacterRecognition
	get_image_bbox --> OpticalCharacterRecognition
	page_no --> OpticalCharacterRecognition
	visible_page_positions --> OpticalCharacterRecognition
	selectable_page_positions --> OpticalCharacterRecognition
	data -->|get| OpticalCharacterRecognition
	OpticalCharacterRecognition -->|overload| get_text
	OpticalCharacterRecognition -->|write| data
	
	data -->|get| AIConfigure
	AIConfigure -->|set| get_AI_configuration
	AIConfigure -->|write| data

	get_selected_text --> Summary
	doc --> Summary
	get_text --> Summary
	get_AI_configuration --> Summary
	Summary -->|弹窗| Tk

	get_text --> MindMap
	doc --> MindMap
	get_AI_configuration --> MindMap
	MindMap -->|弹窗| Tk
```

## 需求文档

**视图界面**：

- [x] [View.md](View.md) 
- [x] [Select&Drag.md](Select&Drag.md) 

**OCR**：

- [x] [OCR.md](OCR.md) 

**AI**：

- [x] [AIConfigure.md](AIConfigure.md) 
- [x] [Summary.md](Summary.md) 
- [x] [MindMap.md](MindMap.md) 
