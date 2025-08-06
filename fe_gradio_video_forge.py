import gradio as gr
import os
import zipfile
import shutil
import asyncio
import tempfile
import threading
import random
import time
from datetime import datetime

    
TEMP_DIR = tempfile.gettempdir()
    
# 自定义 CSS 样式
custom_css = """
.gradio-container {
    max-width: 1280px;
    min-width: 1280px;
    margin: auto;
    padding: 20px;
}
.gr-video video {
    width: 100% !important;
    height: auto !important;
    max-height: 40vh !important;
    object-fit: contain !important;
    display: block !important;
    margin: auto !important;
}
.gr-column {
    min-width: 300px;
}
"""


NUM_WORKERS = 2 #线程数
SIMULATE_TEST_MODE = True #测试模式
task_status_info:dict[str,str] = {
    'READY':'就绪',
    'RUNNING':'运行中',
    'FINISH':'完成',
    'FAILURE':'失败',
}



def generate_test_upload_video_bg(demo):
    gr.Markdown("## 🎬 视频上传测试DEMO")
    with gr.Tabs():
        with gr.TabItem("视频上传"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### 上传或者在换装页面中生成模特")
                    vt_src_image = gr.Image(
                        sources=["upload"],
                        type="filepath",
                        label="换装模特",
                        width=512,
                        height=640,
                    )
                    gr.Examples(
                        inputs=vt_src_image,
                        examples_per_page=9,
                        examples=[],
                        label='示例')
                    
                    vton_gen_img_set = gr.Dataset(
                        components=[
                            gr.Image(visible=False), 
                        ],
                        samples=[],
                        label="我的模特",
                        type="index",
                        samples_per_page=9
                    )
            
                with gr.Column():
                    gr.Markdown("#### 上传驱动动作视频")
                    vt_input_video = gr.Video(
                        label="动作视频",
                        interactive=True, 
                        autoplay=True,
                        elem_id="vt_input_video", 
                        elem_classes=['vt_input_driven_video'],
                        width=512,
                        height=640,)
                    gr.Examples(
                        inputs=vt_input_video,
                        examples_per_page=9,
                        examples=[],
                        label='示例')
                                    
        
                with gr.Column():
                    gr.Markdown("#### 设置和生成结果")
                    vton_gen_video = gr.Video(
                            label="生成视频",
                            interactive=False, 
                            width=512,
                            height=640,
                            show_download_button=True,
                            autoplay=True
                    )
                    vton_gen_video_set = gr.Dataset(
                        components=[
                            gr.Video(visible=False), 
                        ],
                        samples=[],
                        label="生成视频列表",
                        type="index",
                        samples_per_page=9)
                    
                    
                    vt_gen_button = gr.Button("添加任务", interactive=True)
                    with gr.Accordion("任务队列", open=True, visible=True):
                        task_group_dropdown = gr.Dropdown(
                                choices=[],
                                interactive=True,
                                allow_custom_value = False,
                                label="任务"
                        )
                        with gr.Row():
                            task_remove_btn  = gr.Button("删除任务", scale=1, min_width=0, size='md')
                            task_rest_btn    = gr.Button("重置任务", scale=1, min_width=0, size='md')
                            task_refresh_btn = gr.Button("刷新列表", scale=1, min_width=0, size='md')
                            
                        task_group_dataset = gr.Dataset(
                            components=[
                                gr.Image(visible=False,   label="模特", container=False), 
                                gr.Video(visible=False,   label="动作", container=False), 
                                gr.Textbox(visible=False, label="状态", container=False)
                            ],
                            samples=[],
                            label="当前任务列表",
                            type="index",
                            samples_per_page=5)
    
    #任务队列
    task_lock = threading.Lock()  # 保护共享状态
    task_gallery_dict:dict[str, dict] = {} #任务数据
    task_previous_dataset:list = [] #for changing monitor
    

    def task_running_process(task_data: dict):
        if SIMULATE_TEST_MODE:
            duration = random.uniform(2, 5)  # 2-5秒处理时间
            time.sleep(duration)
            gen_result_vton_video, success = './test_video.mp4', random.random() > 0.2
            
        if success:
            return task_status_info['FINISH'], gen_result_vton_video
        else:
            return task_status_info['FAILURE'], None

    def task_worker(worker_id):
        """后台工作线程函数"""
        print(f'[视频换装任务] 后台工作线程: Worker[{worker_id}] working ...')
        while True:
            task_to_process = None
            task_key = None

            # 查找一个“就绪”的任务
            with task_lock:
                for k, v in task_gallery_dict.items():
                    if v["status"] == task_status_info['READY']:
                        task_to_process = v.copy()
                        task_key = k
                        v["status"] = task_status_info['RUNNING']
                        v["cost_time"] = time.time() #当前时间
                        break  # 只取一个

            if task_to_process:
                print(f"[视频换装任务] Worker:[{worker_id}] 开始处理: {task_key}")
                status, gen_result_vton_video = task_running_process(task_to_process)

                # 更新状态
                cost_time = 0
                with task_lock:
                    if task_key in task_gallery_dict:
                        cost_time = time.time() - task_gallery_dict[task_key]["cost_time"]
                        task_gallery_dict[task_key]["status"] = status
                        task_gallery_dict[task_key]["cost_time"] = cost_time
                        task_gallery_dict[task_key]["gen_result_vton_video"] = gen_result_vton_video
                        
                        
                print(f"Worker:[{worker_id}] 完成: {task_key} -> {status}, 耗时：{round(cost_time,2)}s")

            else:
                time.sleep(0.5)  # 没有任务，稍等
                # print(f"Worker 当前没有任务: {len(task_gallery_dict)} ...")
            
    
    def task_remove(cur_item):
        with task_lock:
            if cur_item in task_gallery_dict:
                if task_gallery_dict[cur_item]['status'] == task_status_info['RUNNING']:
                    print(f'[视频换装任务]:[{cur_item}]进行中，请稍后再试')
                
            task_gallery_dict.pop(cur_item)
    
    def task_add(gen_params):
        with task_lock:
            param_vt_id        = gen_params.get('vt_id', None)
            param_vt_src_image = gen_params.get('vt_src_image', None)
            param_vt_input_video = gen_params.get('vt_input_video', None)
            print('[视频换装任务] add_task', param_vt_id)
            if param_vt_id is None:
                raise gr.Error("请先正确设置必要的参数：模特图片，模型动作视频")
            gen_params.pop('vt_id')
            task_gallery_dict.update({param_vt_id:gen_params})
        
    def refresh_task_data(cur_item, fore_refresh = False):
        with task_lock:
            print('[视频换装任务] refresh_task_data, count', len(task_gallery_dict))
            group_choices = []
            gallery_ds = []
            gen_result_vton_videos = []
            for k, v in reversed(task_gallery_dict.items()):
                group_choices += [k]
                status = v['status']
                if status != task_status_info['READY']:
                    cost_time = v['cost_time']
                    if cost_time > 1.e9:
                        cost_time = time.time() - cost_time
                        #ensure to update for the status of 'finish'
                        if status == task_status_info['FINISH']:
                            v['cost_time'] = cost_time
                            
                            
                    status += f"(已耗时：{round(cost_time, 2)}s)"
                    
                gallery_ds += [[v['vt_src_image'], v['vt_input_video'], status]]
    
                if 'gen_result_vton_video' in v and v['gen_result_vton_video'] is not None:
                    gen_result_vton_videos += [[v['gen_result_vton_video']]]
                
            if cur_item not in task_gallery_dict:
                cur_item = None
            
            #check if ds changed.
            ds_changed = fore_refresh or (gallery_ds != task_previous_dataset)
            task_previous_dataset.clear()
            for v in gallery_ds:
                task_previous_dataset.append(v)
        
        
        print(f'==>[视频换装任务] ds_changed?', ds_changed)
        return  gr.update(choices=group_choices, value=cur_item) if ds_changed else gr.update(),\
                gr.update(samples = gallery_ds) if ds_changed else gr.update(),\
                gr.update(samples=gen_result_vton_videos) if ds_changed else gr.update()
       
        
    def reset_task_data(cur_item):
        with task_lock:
            print(f'[图片换装任务] 指定任务重置-{cur_item}')
            if cur_item in task_gallery_dict:
                v = task_gallery_dict[cur_item]
                status = v['status']
                if status == task_status_info['FINISH'] or status == task_status_info['FAILURE']:
                    v.pop('cost_time')
                    v['status'] = task_status_info['READY']         
                    
                       
    
    task_remove_btn.click(
        fn = task_remove,
        inputs=[task_group_dropdown],
        outputs=None
    ).then(
        fn = refresh_task_data,
        inputs=[task_group_dropdown],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
        
        
    task_refresh_btn.click(
        fn = refresh_task_data,
        inputs=[task_group_dropdown],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
    
    task_rest_btn.click(
        fn = reset_task_data,
        inputs=[task_group_dropdown]
    ).then(
        fn = refresh_task_data,
        inputs=[task_group_dropdown],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
    
    
    
    
    task_input_gen_params = gr.State({}) #临时gen params.
    vt_gen_button.click(
            fn=lambda param_vt_src_image,param_vt_input_video: {
                        'vt_id': None if (param_vt_src_image is None or param_vt_input_video is None ) else (f'{os.path.basename(param_vt_src_image)}+{os.path.basename(param_vt_input_video)}'),
                        'vt_src_image':param_vt_src_image,
                        'vt_input_video':param_vt_input_video,
                        'status': task_status_info['READY'],
                },
            inputs=[
                vt_src_image,
                vt_input_video,
            ],
            outputs=[
                task_input_gen_params
            ]
    ).then(
        fn = task_add,
        inputs=[task_input_gen_params],
        outputs=None
    ).then(
        fn = refresh_task_data,
        inputs=[task_group_dropdown],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
    
    
    def on_vton_gen_video_set_select(evt: gr.SelectData):
        print(f"Index: {evt.index}, Value: {evt.value}")
        return evt.value[0]['video']['path']
    
    vton_gen_video_set.select(
        fn=on_vton_gen_video_set_select,
        inputs=None,
        outputs=vton_gen_video
    )
    
    def on_task_group_dataset_select(evt: gr.SelectData):
        print(f"Index: {evt.index}, Value: {evt.value}")
        if isinstance(evt.value[0], dict):
            return f"{os.path.basename(evt.value[0]['path'])}+{os.path.basename(evt.value[1]['video']['path'])}"
        return ''
        
    task_group_dataset.select(
        fn=on_task_group_dataset_select,
        inputs=None,
        outputs=task_group_dropdown
    )
    
    
    
    #不确定这个刷新逻辑是否可能会造成gradio连接断续， 从而造成访问502
    timer_component = gr.Timer(value=5)
    timer_component.tick(
        #刷新界面
        fn = refresh_task_data,
        inputs=[task_group_dropdown],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
    
    
    
    #启动线程
    demo.queue()
    threadings = []
    # --- 启动任务后台工作线程 ---
    def on_task_started(*args):
        if len(threadings) == 0:
            for i in range(NUM_WORKERS):
                t = threading.Thread(target=task_worker, args=(i+1,), daemon=True)
                t.start()
                threadings.append(t)
        print(f'[视频换装]启动{NUM_WORKERS}个后台任务线程: 图片换装 ...')

    # 利用 startup 事件启动工作线程
    demo.load(
        fn=on_task_started, inputs=None, outputs=None
    ).then(
        fn = refresh_task_data,
        inputs=[task_group_dropdown, gr.State(True)],
        outputs=[task_group_dropdown, task_group_dataset, vton_gen_video_set]
    )
    
    

if __name__ == "__main__":
    ap = [
        #add some paths
        os.path.abspath('.')
    ]
    print('Allowed paths:')
    print(ap)
    # 初始化界面
    with gr.Blocks(css=custom_css, title="视频上传测试DEMO", theme=gr.themes.Glass()) as demo:
        with gr.Tabs():
            with gr.TabItem("视频上传"):
                generate_test_upload_video_bg(demo)

    demo.launch(server_name='0.0.0.0', 
                server_port=8100,
                allowed_paths=ap,
    )