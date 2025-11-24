# 服务项目评标报告模板 
SERVICE_EVALUATION_REPORT_TEMPLATES = {
    "评标报告": {
        "template": """
        <p><br></p>
        <p><br></p>
        <p style="text-align: center;line-height: 1.5">{% if 项目名称 is none or 项目名称 == "" or 项目名称 == "______" %}<span id="项目名称" style="background-color: rgb(255,255,0); font-family: 宋体; font-size: 29px;">______</span>{% else %}<span id="项目名称" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 29px;">{项目名称}</span>{% endif %}</p>
        <p style="text-align: center;"><span style="font-family: 楷体; font-size: 24px;">（招标编号：</span><span id="招标编号" style="background-color: rgb(192,192,192);font-family: 楷体; font-size: 24px;">{% if 招标编号 is none or 招标编号 == "" or 招标编号 == "______" %}______{% else %}{招标编号}{% endif %}</span><span style="font-family: 楷体; font-size: 24px;">/</span><span id="标段号" style="background-color: rgb(192,192,192);font-family: 楷体; font-size: 24px;">{% if 标段号 is none or 标段号 == "" or 标段号 == "______" %}______{% else %}{标段号}{% endif %}</span><span style="font-family: 楷体; font-size: 24px;">）</span></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>       
        <p><br></p>
        <p><br></p>        
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p style="text-align: center;"><span style="font-size: 48px; font-family: 宋体;"><strong>评 标 报 告</strong></span></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p><br></p>
        <p style="text-align: left; text-indent: 2em;line-height: 1.5"><span style="font-family: 宋体; font-size: 24px;">招标人：</span><span id="招标人" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 24px;">{% if 招标人 is none or 招标人 == "" or 招标人 == "______" %}______{% else %}{招标人}{% endif %}</span></p>
        <p style="text-align: left; text-indent: 2em;line-height: 1.5"><span style="font-family: 宋体; font-size: 24px;">招标代理：</span><span id="招标代理" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 24px;">{% if 招标代理 is none or 招标代理 == "" or 招标代理 == "______" %}______{% else %}{招标代理}{% endif %}</span></p>
        <p style="text-align: center;"><span id="生成日期" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 24px;">{% if 生成日期 is none or 生成日期 == "" or 生成日期 == "______" %}______{% else %}{生成日期}{% endif %}</span></p>
        <!--pagebreak-->
        <p style="text-indent:2em;">{% if 项目名称 is none or 项目名称 == "" or 项目名称 == "______" %}<span id="项目名称" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="项目名称" style="background-color: rgb(192,192,192);">{项目名称}</span>{% endif %}［招标编号/标段号：{% if 招标编号 is none or 招标编号 == "" or 招标编号 == "______" %}<span id="招标编号" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="招标编号" style="background-color: rgb(192,192,192);">{招标编号}</span>{% endif %}/{% if 标段号 is none or 标段号 == "" or 标段号 == "______" %}<span id="标段号" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="标段号" style="background-color: rgb(192,192,192);">{标段号}</span>{% endif %}］，已完成开评标程序。现将开评标情况报告如下：</p>
        <h1>一、项目基本情况</h1>
        <h2>1、项目概况</h2>
        <p style="text-indent:2em;">招标单位：{% if 招标人 is none or 招标人 == "" or 招标人 == "______" %}<span id="招标人" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="招标人" style="background-color: rgb(192,192,192);">{招标人}</span>{% endif %}</p>
        <p style="text-indent:2em;">项目名称：{% if 项目名称 is none or 项目名称 == "" or 项目名称 == "______" %}<span id="项目名称" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="项目名称" style="background-color: rgb(192,192,192);">{项目名称}</span>{% endif %}</p>
        <p style="text-indent:2em;">招标代理机构：{% if 招标代理 is none or 招标代理 == "" or 招标代理 == "______" %}<span id="招标代理" style="background-color: rgb(255,255,0);">______</span>{% else %}<span id="招标代理" style="background-color: rgb(192,192,192);">{招标代理}</span>{% endif %}</p>
        <p style="text-indent:2em;">招标方式：{招标方式}</p>
        <p style="text-indent:2em;">招标内容及范围：详见招标文件</p>
        <p style="text-indent:2em;">项目地点：{建设地点或交货地点或项目地点}</p>
        <p style="text-indent:2em;">服务期限：{交货期或计划工期或服务期限}</p>
        <p style="text-indent:2em;">质量要求：{质量要求}</p>
        <p style="text-indent:2em;">资格审查方式：资格后审。</p>
        <h2>2、招标公告发布时间及媒体</h2>
        <p style="text-indent:2em;">本项目于{公告发布时间}在{公告发布网站}发布招标公告。公告载明愿意参加本项目潜在投标人可于{获取招标文件时间}至{获取文件截止时间}（北京时间），登录《晋能控股招标采购平台》在线获取招标文件。</p>
        <h2>3、招标文件获取情况</h2>
        <p style="text-indent:2em;">截止{获取文件截止时间}，共有{潜在投标人数}家潜在投标人在线获取了本项目的招标文件。</p>
        <h1>二、评标委员会组成</h1>
        <p style="text-indent:2em;">本招标项目评标委员会由{评标委员会人数}人组成，从{抽取专家库名称}随机抽取了{专家人数}名专家，与{招标人代表人数}名招标人代表共同组成评标委员会，评标委员会主任委员由评标委员会全体人员推荐产生，名单如下：</p>
        <p style="text-indent:2em;">评标委员会主任：{评标委员会主任}</p>
        <p style="text-indent:2em;">其他评标委员会成员：{其他评标委员会成员}</p>
        <h1>三、开标情况</h1>
        <p style="text-indent:2em;">至投标截止时间{投标截止时间}，有{有效投标人数}家投标人通过《晋能控股招标采购平台》在线递交了投标文件。</p>
        <p style="text-indent:2em;">开标记录详见下表：</p>
        {% if 开标记录表格 is none or 开标记录表格 == "" or 开标记录表格 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>序号</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标人名称</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标报价（万元）</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>...</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>备注</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="2"><span style="font-family: 宋体;">最高投标限价</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="3">{最高投标限价}</td>
            </tr>
        </table>
        {% else %}
            {开标记录表格}
        {% endif %}
        <h1>四、评标办法、因素及标准</h1>
        <p style="text-indent:2em;">1、评标办法：本次评标采用{评标办法}</p>
        {% if 分值部分 is none or 分值部分 == "" or 分值部分 == "______" %}
            <p style="text-indent:2em;">2、评标因素与标准：满分为{评标因素标准}。其中资信商务部分：______分，投标报价部分：______分，技术服务部分：______分，其他因素部分：______分。</p>
        {% else %}
            <p style="text-indent:2em;">2、评标因素与标准：满分为{评标因素标准}。其中{分值部分}。</p>
        {% endif %}
        <h1>五、评标过程及情况</h1>
        <h2>1、评标过程</h2>
        <p style="text-indent:2em;">开标议程结束后，由招标代理公司主持，召开了本项目的评标会议。评标委员会依据评标办法对所有投标人的投标文件进行了初步评审，并对通过初步评审的投标文件进行了详细评审。工作组协助评标委员会依据投标报价评分标准计算出投标人的报价得分，评标专家对商务和技术部分进行详细评审，汇总各投标人综合得分并进行了排序（详见评审结果）。</p>
        <h2>2、否决投标情况说明</h2>
        {% if 否决投标情况说明 is none or 否决投标情况说明 == "" or 否决投标情况说明 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标人名称</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>招标文件要求</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标人在投标文件中所附材料</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>评标委员会评审结论</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
        </table>
        {% else %}
            {否决投标情况说明}
        {% endif %}
        <h2>3、澄清、说明、补正事项纪要</h2>
        <p style="text-indent:2em;">{澄清说明补正事项纪要}</p>
        <h2>4、评审结果</h2>
         <p style="text-indent:2em;">对符合初步评审要求的投标人，评标委员会全体成员经过详细评审，评审结果如下：</p>
        {% if 评审结果 is none or 评审结果 == "" or 评审结果 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>序号</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标人名称</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>合计得分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>排名</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>备注</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;">1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
        </table>
        {% else %}
            {评审结果}
        {% endif %}
        <h1>六、推荐中标候选人名称</h1>
        {% if 推荐中标候选人名称 is none or 推荐中标候选人名称 == "" or 推荐中标候选人名称 == "______" %}
        <p style="text-indent:2em;">根据招标文件规定，推荐了<span style="background-color: rgb(255,255,0);">______</span>名中标候选人。<span style="background-color: rgb(255,255,0);">______</span>为第一中标候选人；<span style="background-color: rgb(255,255,0);">______</span>为第二中标候选人。具体情况如下：</p>
        {% else %}
        <p style="text-indent:2em;">{推荐中标候选人名称}</p>
        {% endif %}
        <h2>1、中标候选人得分汇总情况如下：</h2>
        {% if 中标候选人得分汇总情况 is none or 中标候选人得分汇总情况 == "" or 中标候选人得分汇总情况 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>序号</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>候选人名称</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标报价</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>修正后报价</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>资信商务得分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>技术服务得分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>投标报价得分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>其他部分得分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>总分</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;"><strong>排名</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
        </table>
        {% else %}
            {中标候选人得分汇总情况}
        {% endif %}
        <h2>2、中标候选人资质、资格业绩等评审情况</h2>
        {% if 中标候选人资质资格业绩等评审情况表格 is none or 中标候选人资质资格业绩等评审情况表格 == "" or 中标候选人资质资格业绩等评审情况表格 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2"><span style="font-family: 宋体;font-size: 14px;"><strong>序号</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2"><span style="font-family: 宋体;font-size: 14px;"><strong>初步评审内容</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="3"><span style="font-family: 宋体;font-size: 14px;"><strong>评审情况</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">资质</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">2</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">项目负责人</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">3</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">业绩1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
        </table>
        {% else %}
            {中标候选人资质资格业绩等评审情况表格}
        {% endif %}
        <h2>3、中标候选人详细评审客观分得分情况</h2>
        {% if 中标候选人详细评审客观分得分情况表格 is none or 中标候选人详细评审客观分得分情况表格 == "" or 中标候选人详细评审客观分得分情况表格 == "______" %}
        <table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2"><span style="font-family: 宋体;font-size: 14px;"><strong>序号</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2" colspan="2"><span style="font-family: 宋体;font-size: 14px;"><strong>详细评审客观类评标条款</strong></span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="3"><span style="font-family: 宋体;font-size: 14px;"><strong>评审情况</strong></span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2"><span style="font-family: 宋体;font-size: 14px;">1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="2"><span style="font-family: 宋体;font-size: 14px;">供应商近年类似项目业绩</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">业绩1</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">业绩2</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="3"><span style="font-family: 宋体;font-size: 14px;">2</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;" rowspan="3"><span style="font-family: 宋体;font-size: 14px;">三体系认证</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">质量管理体系</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">环境管理体系</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
            <tr>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体;font-size: 14px;">职业健康安全管理体系</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
                <td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(255,255,0); font-family: 宋体;font-size: 14px;">______</span></td>
            </tr>
        </table>
        {% else %}
            {中标候选人详细评审客观分得分情况表格}
        {% endif %}
        <h1>七、签订合同前要处理的事宜</h1>
        <p style="text-indent:2em;">评标结束后，将对中标候选人进行公示，公示结束后无异议，由招标人依法确定中标人，向中标人发放中标通知书，并将中标结果通知所有未中标的投标人。</p>
        <p style="margin: 10px 0;">&nbsp;</p>
        <p>评标委员会成员签名：___________________________________________________</p>
        """,
        "extract_fields": [
            # 中文字段
            "项目名称", "招标编号", "标段号", "招标人", "生成日期","招标代理", "招标方式",
            "招标内容及范围", "交货期或计划工期或服务期限", "建设地点或交货地点或项目地点",
            "质量要求", "公告发布时间", "公告发布网站", "获取招标文件时间", "获取文件截止时间",
            "潜在投标人数", "评标委员会人数", "抽取专家库名称", "专家人数", "招标人代表人数",
            "评标委员会主任", "其他评标委员会成员", "投标截止时间", "有效投标人数",
            "最高投标限价", "评标办法", "评标因素标准", "分值部分", "推荐中标候选人数", "推荐中标候选人名称",
            "第一中标候选人名称", "第二中标候选人名称", "第三中标候选人名称",
            "开标记录表格", "否决投标情况说明", "澄清说明补正事项纪要",
            "评审结果", "中标候选人得分汇总情况", "中标候选人资质和资格业绩等评审情况",
            "中标候选人详细评审客观分得分情况", "中标候选人资质资格业绩等评审情况表格",
            "中标候选人详细评审客观分得分情况表格",

            # 英文字段
            "project_name", "tender_number", "bid_section_number", "generate_date","tenderer", "tender_agent", "tender_method",
            "tender_scope", "delivery_or_service_period", "project_location", "quality_requirements",
            "announcement_date", "announcement_website", "document_obtain_period", "document_deadline",
            "potential_bidders_count", "evaluation_committee_count", "expert_database_name", "experts_count",
            "tenderer_representatives_count", "evaluation_committee_chair", "evaluation_committee_members",
            "bid_deadline", "valid_bidders_count", "bid_opening_records", "max_bid_price",
            "evaluation_method", "evaluation_factors", "bid_score", "bid_rejection_notes", "clarification_summary",
            "evaluation_result", "recommended_candidates_count", "first_candidate_name", "second_candidate_name",
            "third_candidate_name", "fourth_candidate_name", "fifth_candidate_name", "sixth_candidate_name", "candidate_score_summary", "candidate_qualification_review",
            "candidate_detailed_scores", "qualification_review_table", "detailed_score_table"
        ],
        "generate_fields": [
            "evaluation_summary", "contract_terms"
        ]
    }
}
