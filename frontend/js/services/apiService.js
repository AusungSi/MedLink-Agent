// 后端API基础地址（根据实际部署环境修改）
const API_BASE_URL = 'http://localhost:5000/api';
const API_HOST_URL = API_BASE_URL.replace(/\/api$/, '');

// 医生端测试数据：当后端未提供专用接口时使用
const DOCTOR_PATIENTS_FALLBACK = [
  {
    id: 101,
    name: '张三',
    sex: '男',
    age: 45,
    reportText: '超声提示：右叶结节1.2cm，低回声，边界欠清，点状强回声，建议结合临床复查。',
    screening: {
      age: 45,
      sex: '男',
      tsh: 1.8,
      neck_radiation_exposure: false,
      family_thyroid_cancer_history: false,
      characteristics: {
        composition: '实性',
        echogenicity: '低回声',
        shape: '高大于宽',
        margin: '不规则',
        echogenic_foci: '点状强回声'
      },
      report_text: '右叶结节1.2cm，低回声，边界欠清，点状强回声。'
    },
    imageUrls: [
      'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=1200&q=80'
    ]
  },
  {
    id: 102,
    name: '李四',
    sex: '女',
    age: 38,
    reportText: '化验：TSH降低，FT4升高；超声提示弥漫性回声改变，未见明确高危结节。',
    screening: {
      age: 38,
      sex: '女',
      tsh: 0.2,
      neck_radiation_exposure: false,
      family_thyroid_cancer_history: false,
      characteristics: {
        composition: '混合实性',
        echogenicity: '等回声',
        shape: '宽大于高',
        margin: '光滑',
        echogenic_foci: '无'
      },
      report_text: '甲功异常，建议复查。'
    },
    imageUrls: [
      'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1200&q=80'
    ]
  }
];

function normalizeDoctorPatient(raw) {
  const imageUrls = [];
  const rawImagePaths = raw.image_paths || raw.imagePaths || raw['影像资料'] || '';

  if (Array.isArray(raw.imageUrls)) {
    raw.imageUrls.forEach(url => {
      const val = String(url || '').trim();
      if (!val) return;
      if (/^https?:\/\//i.test(val)) {
        imageUrls.push(val);
      } else {
        imageUrls.push(`${API_HOST_URL}${val.startsWith('/') ? '' : '/'}${val}`);
      }
    });
  } else if (Array.isArray(raw.image_urls)) {
    raw.image_urls.forEach(url => {
      const val = String(url || '').trim();
      if (!val) return;
      if (/^https?:\/\//i.test(val)) {
        imageUrls.push(val);
      } else {
        imageUrls.push(`${API_HOST_URL}${val.startsWith('/') ? '' : '/'}${val}`);
      }
    });
  } else if (typeof rawImagePaths === 'string' && rawImagePaths.trim()) {
    rawImagePaths.split(',').map(s => s.trim()).filter(Boolean).forEach(path => {
      if (/^https?:\/\//i.test(path)) {
        imageUrls.push(path);
      } else {
        imageUrls.push(`${API_HOST_URL}${path.startsWith('/') ? '' : '/'}${path}`);
      }
    });
  }

  const screening = raw.screening || {};
  const characteristics = screening.characteristics || raw.characteristics || {};

  return {
    id: raw.id,
    name: raw.name || raw.full_name || raw.patientName || '未命名患者',
    sex: raw.sex || raw.gender || '未知',
    age: Number(raw.age) || 0,
    reportText: raw.reportText || raw.report_text || raw['现病史'] || raw['主诉'] || '',
    imageUrls,
    screening: {
      age: screening.age ?? raw.age ?? null,
      sex: screening.sex || raw.sex || raw.gender || '',
      tsh: screening.tsh ?? raw.tsh ?? null,
      neck_radiation_exposure: screening.neck_radiation_exposure ?? raw.neck_radiation_exposure ?? null,
      family_thyroid_cancer_history: screening.family_thyroid_cancer_history ?? raw.family_thyroid_cancer_history ?? null,
      characteristics: {
        composition: characteristics.composition || '',
        echogenicity: characteristics.echogenicity || '',
        shape: characteristics.shape || '',
        margin: characteristics.margin || '',
        echogenic_foci: characteristics.echogenic_foci || ''
      },
      report_text: screening.report_text || raw.reportText || raw.report_text || ''
    }
  };
}

function mapDoctorWorkflowToDecisionChain(nodeResults) {
  /**
   * 后端驱动的决策链条映射：优先使用后端真实返回的 nodeResults，
   * 不再前端拼装。保证与后端执行逻辑一致。
   */
  const safeNodeResults = nodeResults || {};
  return {
    nodes: [
      {
        id: 'n1',
        status: safeNodeResults.n1?.status || 'idle',
        result: safeNodeResults.n1?.result || '',
        doctorInstruction: safeNodeResults.n1?.doctorInstruction || '',
        patientBasicInfo: safeNodeResults.n1?.patientBasicInfo || '',
        timestamp: safeNodeResults.n1?.timestamp
      },
      {
        id: 'n2',
        status: safeNodeResults.n2?.status || 'idle',
        result: safeNodeResults.n2?.result || '',
        structuredInfo: safeNodeResults.n2?.structuredInfo || '',
        timestamp: safeNodeResults.n2?.timestamp
      },
      {
        id: 'n3',
        status: safeNodeResults.n3?.status || 'idle',
        result: safeNodeResults.n3?.result || '',
        scoreBasis: safeNodeResults.n3?.scoreBasis || '',
        timestamp: safeNodeResults.n3?.timestamp
      },
      {
        id: 'n4',
        status: safeNodeResults.n4?.status || 'idle',
        result: safeNodeResults.n4?.result || '',
        featureAnalysis: safeNodeResults.n4?.featureAnalysis || '',
        microCalcResult: safeNodeResults.n4?.microCalcResult || safeNodeResults.n4?.featureAnalysis || '',
        timestamp: safeNodeResults.n4?.timestamp
      },
      {
        id: 'n5',
        status: safeNodeResults.n5?.status || 'idle',
        result: safeNodeResults.n5?.result || '',
        finalSummary: safeNodeResults.n5?.finalSummary || '',
        finalReport: safeNodeResults.n5?.finalReport || '',
        timestamp: safeNodeResults.n5?.timestamp
      }
    ],
    edges: [
      { from: 'n1', to: 'n2' },
      { from: 'n2', to: 'n3' },
      { from: 'n3', to: 'n4' },
      { from: 'n4', to: 'n5' }
    ]
  };
}

function normalizeDoctorThyroidReportResponse(raw, question) {
  /**
   * 后端驱动的响应标准化：不拼装，直接使用后端返回的字段。
   * 确保前端严格依赖后端数据，避免降级生成虚假结果。
   */
  const normalizedPatients = Array.isArray(raw?.patientReports)
    ? raw.patientReports.map(normalizeDoctorPatient)
    : [];

  // 直接使用后端返回的证据列表（已包含 source 和 confidence）
  const evidence = Array.isArray(raw?.evidence)
    ? raw.evidence.map((ev) => ({
      title: ev?.title || '证据项',
      body: ev?.body || '',
      quote: ev?.quote || ev?.body || '',
      source: ev?.source || '医学知识库',
      confidence: ev?.confidence || '-'
    }))
    : [];

  // 直接使用后端返回的 imageEvidence（包含标记坐标和定位信息）
  const imageEvidence = raw?.imageEvidence || {
    title: '暂无可定位影像',
    imageUrl: '',
    marker: { x: 50, y: 50 },
    finding: '后端未返回影像证据定位信息'
  };

  // 直接使用后端返回的 nodeResults 构建决策链条
  const decisionChain = mapDoctorWorkflowToDecisionChain(
    raw?.nodeResults || {},
    raw?.workflow || []
  );

  const answer = raw?.answer || '未获得诊疗报告';
  
  return {
    answer,
    patientReports: normalizedPatients,
    workflow: Array.isArray(raw?.workflow) ? raw.workflow : [],
    evidence,
    imageEvidence,
    decisionChain,
    runId: raw?.runId || `run-${Date.now().toString().slice(-6)}`
  };
}

/**
 * 辅助函数：获取认证请求头
 * @returns {Object} 包含认证信息的请求头配置
 * @throws {Error} 当没有找到有效的token时抛出错误
 */
function getAuthHeaders() {
  // 从localStorage获取登录时保存的token
  const token = localStorage.getItem('access_token');
  
  /**
 * 工具函数：保存登录状态到本地存储（新增）
 * @param {string} token - 认证Token（与现有逻辑一致，使用access_token键名）
 * @param {Object} user - 用户信息对象
 */
function saveLoginState(token, user) {
  localStorage.setItem('access_token', token);
  localStorage.setItem('user_info', JSON.stringify(user)); // 新增用户信息存储（可选）
}

/**
 * 工具函数：清除本地登录状态（新增）
 */
function clearLoginState() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_info');
}

/**
 * 工具函数：检查是否已登录（新增）
 * @returns {boolean} 登录状态（true=已登录，false=未登录）
 */
function isLoggedIn() {
  return !!localStorage.getItem('access_token');
}

/**
 * 工具函数：从本地存储获取当前用户信息（新增）
 * @returns {Object|null} 用户信息（无登录状态时返回null）
 */
function getCurrentUserFromStorage() {
  const userStr = localStorage.getItem('user_info');
  return userStr ? JSON.parse(userStr) : null;
}

  // 验证token是否存在
  if (!token) {
    throw new Error('用户未登录或token已过期');
  }
  
  // 返回包含认证信息的请求头
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}` // JWT认证格式
  };
}

const apiService = {
  /**
   * 用户登录接口（新增）
   * 对应后端接口：POST /api/auth/login 
   */
  login: async function(phone, password, userType) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({
          phone,
          password,
          user_type: userType
        }),
        credentials: 'include'
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || `登录失败: ${response.statusText}`);
      }

      // 登录成功后保存token到localStorage
      if (data.data && data.data.token) {
        // 根据文档 [cite: 1021]，token 在 data.token 中
        localStorage.setItem('access_token', data.data.token);
      }

      return data;
    } catch (error) {
      console.error('login API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 患者注册接口（新增 - 已修正BUG）
   * 对应后端接口：POST /api/auth/register/patient [cite: 960]
   */
  registerPatient: async function(phone, password, fullName, birthDate) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register/patient`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          phone,
          password,
          // --- 关键修正 ---
          // 后端 schema (auth_schema.py) 需要 'full_name' 而不是 'real_name'
          full_name: fullName, 
          // ------------------
          birth_date: birthDate
        }),
        credentials: 'include'
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.msg || `患者注册失败: ${response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('registerPatient API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 医生注册接口（新增）
   * 对应后端接口：POST /api/auth/register/doctor 
   * (注意：请确保您的表单也提交了 'full_name' 字段，后端 schema 需要它)
   */
  registerDoctor: async function(phone, password, fullName, licenseId, hospital, department, title, certificateFile) {
    try {
      const formData = new FormData();
      formData.append('phone', phone);
      formData.append('password', password);
      formData.append('full_name', fullName); // <--- 建议添加此字段以匹配后端
      formData.append('license_id', licenseId);
      formData.append('hospital', hospital);
      formData.append('department', department);
      formData.append('title', title);
      formData.append('certificate', certificateFile);

      const response = await fetch(`${API_BASE_URL}/auth/register/doctor`, {
        method: 'POST',
        headers: {
          // FormData无需设置Content-Type
        },
        body: formData,
        credentials: 'include'
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.msg || `医生注册失败: ${response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('registerDoctor API调用失败:', error.message);
      throw error;
    }
  },
  /**
   * 获取当前登录用户信息
   * 对应后端需要JWT认证的接口：GET /api/user/current
   */
  getCurrentUser: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/user/current`, {
        method: 'GET',
        headers: getAuthHeaders(), // 使用认证头
        credentials: 'include'
      });

      // 先解析响应数据
      const data = await response.json();

      // 处理401未授权错误（用户未登录）
      if (response.status === 401) {
        // 清除无效token
        localStorage.removeItem('access_token');
        // 使用接口返回的错误信息，如果没有则使用默认信息
        throw new Error(data.message || '用户未登录');
      }

      if (!response.ok) {
        throw new Error(`获取用户信息失败: ${data.message || response.statusText}`);
      }

      // 直接返回用户信息对象（根据文档，成功响应直接是用户信息对象）
      return data;
    } catch (error) {
      console.error('getCurrentUser API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取最近一条问诊记录（需要认证）
   * 对应后端接口：GET /api/history/recent
   * @returns {Promise<Object|null>} 最近一条问诊记录对象，无记录时返回null
   */
  getRecentMedicalRecord: async function() {
    try {
      // 发起带认证的GET请求，使用新的接口路径
      const response = await fetch(`${API_BASE_URL}/history/recent`, {
        method: 'GET',
        headers: getAuthHeaders(), // 使用认证头
        credentials: 'include'
      });

      // 处理401未授权错误
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      // 处理500服务器错误
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }

      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
      }

      // 根据API文档，无记录时返回null，有记录时返回对象
      const record = await response.json();
      
      // 验证返回数据格式
      if (record !== null && (typeof record !== 'object' || Array.isArray(record))) {
        throw new Error('后端返回数据格式错误：应为对象或null');
      }

      return record;

    } catch (error) {
      console.error('getRecentMedicalRecord API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取全部问诊记录（需要认证，无分页）
   * 对应后端接口：GET /api/history/all
   * @returns {Promise<Array>} 所有问诊记录组成的数组
   */
  getAllMedicalRecords: async function() {
    try {
      // 直接使用基础URL，不添加分页参数
      const response = await fetch(`${API_BASE_URL}/history/all`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      // 处理401未授权错误
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      // 处理500服务器错误
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }

      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
      }

      // 获取所有记录列表
      const records = await response.json();
      
      // 验证返回数据格式应为数组
      if (!Array.isArray(records)) {
        throw new Error('后端返回数据格式错误：应为数组');
      }

      return records;

    } catch (error) {
      console.error('getAllMedicalRecords API调用失败:', error.message);
      throw error;
    }
  },
  
  /**
   * 发送医疗问题到AI模型，获取诊断建议
   * 后端接口：POST /api/chat/medical
   * @param {string} question 用户的问题
   * @returns {Promise<string>} AI返回的诊断建议
   */
  sendMedicalQuery: async function(question) {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/medical`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`请求失败: ${errorData.message || response.statusText}`);
      }

      const data = await response.json();
      return data.answer; // 假设后端返回 { "answer": "AI回答内容" }
    } catch (error) {
      console.error('sendMedicalQuery 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 医生工作站：携带患者标签时生成甲状腺完整报告
   * 后端接口：POST /api/chat/doctor/thyroid/report
   * @param {string} question 医生输入的问题
   * @param {Array<number|string>} patientIds 被标签选中的患者ID
   * @returns {Promise<{answer:string, patientReports:Array, workflow:Array, evidence:Array, imageEvidence:Object, decisionChain:Object, runId:string}>}
   */
  sendDoctorThyroidReport: async function(question, patientIds) {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/doctor/thyroid/report`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, patient_ids: patientIds }),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || `请求失败: ${response.statusText}`);
      }

      return normalizeDoctorThyroidReportResponse(data, question);
    } catch (error) {
      console.error('sendDoctorThyroidReport 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 发送医疗问题和文件到AI模型，获取诊断建议
   * 后端接口：POST /api/chat/medical/upload
   * @param {string} question 用户的问题
   * @param {Array<File>} files 文件数组
   * @returns {Promise<string>} AI返回的诊断建议
   */
  sendMedicalQueryWithFiles: async function(question, files) {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error('用户未登录或token已过期');
      const formData = new FormData();
      formData.append('question', question);
      files.forEach(f => formData.append('files', f));
      const response = await fetch(`${API_BASE_URL}/chat/medical/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
        credentials: 'include'
      });
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || response.statusText);
      }
      const data = await response.json();
      return data.answer;
    } catch (error) {
      console.error('sendMedicalQueryWithFiles 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 甲状腺筛查（病人端结构化采集 + 影像/报告上传）
   * 说明：调用后端专用接口，流程为“先入库 -> TI-RADS真实计算 -> AI建议”
   *
   * @param {Object} payload 结构化信息（年龄/性别/TSH/危险因素/TI-RADS特征/报告文本）
   * @param {Array<File>} files 影像或报告文件
   * @returns {Promise<{answer: string, tiRads: Object, payloadEcho: Object}>}
   */
  submitThyroidScreening: async function(payload, files = []) {
    try {
      // 调用专用后端接口：先入库 + TI-RADS真实计算 + 再调用AI
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error('用户未登录或token已过期');
      const formData = new FormData();
      formData.append('screening_payload', JSON.stringify(payload || {}));
      (files || []).forEach(f => formData.append('files', f));

      const response = await fetch(`${API_BASE_URL}/chat/thyroid/screening`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
        credentials: 'include'
      });
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || response.statusText);
      }
      const data = await response.json();
      const answer = data.answer || '';
      const tiRads = data.tiRads || null;

      return {
        answer,
        tiRads,
        payloadEcho: payload
      };
    } catch (error) {
      console.error('submitThyroidScreening 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 创建AI问诊历史对话记录
   * 后端接口：POST /api/history/create
   * @param {string} question 用户问题
   * @param {string} answer AI回答
   * @returns {Promise<Object>} 保存的历史记录对象
   */
  createMedicalRecord: async function(question, answer) {
    try {
      const response = await fetch(`${API_BASE_URL}/history/create`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          answer
        }),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`创建记录失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('createMedicalRecord 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取AI问诊历史对话记录
   * 后端接口：GET /api/chat/history
   * @returns {Promise<Array>} 历史对话数组，格式为 [{question: "用户问题", answer: "AI回答", createdAt: "时间戳"}, ...]
   */
  getMedicalChatHistory: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/history`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取历史记录失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('getMedicalChatHistory 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 通知后端开启新的对话
   * 后端接口：POST /api/chat/new
   * @returns {Promise<Object>} 后端返回的确认信息
   */
  startNewMedicalChat: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/new`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`开启新对话失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('startNewMedicalChat 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 生成病历并保存
   * 后端接口：POST /api/chat/medical/record
   * @returns {Promise<Object>} AI生成的病历对象
   */
  generateMedicalRecord: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/medical/record`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }
      
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`生成病历失败: ${errorData.message || response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('generateMedicalRecord 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取所有科室列表
   * 后端接口：GET /api/departments
   */
  getDepartments: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/departments`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取科室失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('getDepartments 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取医生列表（支持按科室筛选）
   * 后端接口：GET /api/doctors?departmentId=xxx
   * @param {string|null} departmentId 科室ID（为空时获取全部医生）
   */
  getDoctors: async function(departmentId = null) {
    try {
      // 构建带筛选参数的URL
      let url = `${API_BASE_URL}/doctors`;
      if (departmentId) {
        url += `?departmentId=${encodeURIComponent(departmentId)}`;
      }

      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取医生列表失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('getDoctors 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 提交医生预约请求
   * 后端接口：POST /api/appointments
   * @param {Object} appointment 预约信息
   */
  createAppointment: async function(appointment) {
    try {
      const response = await fetch(`${API_BASE_URL}/appointments`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(appointment),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`预约失败: ${errorData.message || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('createAppointment 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 获取用户的待处理预约（等待确认状态）
   * 对应后端接口：GET /api/appointments/pending
   * @returns {Promise<Array>} 待处理预约数组
   */
  getPendingAppointments: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/appointments/pending`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      // 处理401未授权错误
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      // 处理服务器内部错误
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误，获取预约信息失败');
      }

      // 处理其他错误状态
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取待处理预约失败: ${errorData.message || response.statusText}`);
      }

      // 解析响应数据（预约数组）
      const pendingAppointments = await response.json();

      // 验证返回数据格式（必须是数组）
      if (!Array.isArray(pendingAppointments)) {
        throw new Error('后端返回预约数据格式错误：预期为数组');
      }

      return pendingAppointments;

    } catch (error) {
      console.error('getPendingAppointments API调用失败:', error.message);
      throw error; // 抛出错误供上层处理
    }
  },


  /**
   * 获取病历记录列表（独立于问诊记录的病历数据）
   * 对应后端接口：GET /api/medical-records
   * @returns {Promise<Array>} 病历记录数组，包含主诉、诊断等完整病历信息
   */
  getMedicalRecords: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/medical-records`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      // 处理401未授权错误（token失效/未登录）
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      // 处理服务器内部错误
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误，获取病历记录失败');
      }

      // 处理其他错误状态码
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取病历记录失败: ${errorData.message || response.statusText}`);
      }

      // 解析响应数据（病历记录数组）
      const medicalRecords = await response.json();

      // 验证返回数据格式（必须是数组）
      if (!Array.isArray(medicalRecords)) {
        throw new Error('后端返回病历记录格式错误：预期为数组');
      }

      return medicalRecords;

    } catch (error) {
      console.error('getMedicalRecords API调用失败:', error.message);
      throw error; // 抛出错误供上层处理
    }
  },


  /**
   * 获取病历详情
   * 对应后端接口：GET /api/medical-records/:id
   * @param {number|string} recordId 病历ID
   * @returns {Promise<Object>} 病历详情对象（包含主诉、现病史等字段）
   */
  getMedicalRecordDetail: async function(recordId) {
    try {
      // 验证参数有效性
      if (!recordId || (typeof recordId !== 'number' && typeof recordId !== 'string')) {
        throw new Error('无效的病历ID');
      }

      // 发起请求获取指定ID的病历详情
      const response = await fetch(`${API_BASE_URL}/medical-records/${recordId}`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      // 处理401未授权错误
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      // 处理404未找到错误
      if (response.status === 404) {
        throw new Error('未找到该病历记录');
      }

      // 处理服务器内部错误
      if (response.status === 500) {
        const errorData = await response.json();
        throw new Error(errorData.message || '服务器内部错误');
      }

      // 处理其他错误状态
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`获取病历详情失败: ${errorData.message || response.statusText}`);
      }

      // 解析并返回病历详情数据
      const recordDetail = await response.json();
      
      // 验证返回数据格式
      if (typeof recordDetail !== 'object' || recordDetail === null) {
        throw new Error('后端返回病历详情格式错误');
      }

      return recordDetail;

    } catch (error) {
      console.error('getMedicalRecordDetail API调用失败:', error.message);
      throw error; // 抛出错误供页面处理
    }
  },

  /**
   * 获取用户详细信息（个人中心使用）
   * 对应后端接口：GET /api/user/info
   * @returns {Promise<Object>} 用户信息对象
   */
  getUserInfo: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/user/info`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error(data.message || '登录已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(`获取用户信息失败: ${data.message || response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('getUserInfo API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 上传用户头像
   * 对应后端接口：POST /api/user/avatar
   * @param {FormData} formData 包含头像文件的FormData对象
   * @returns {Promise<Object>} 包含新头像URL的响应对象
   */
  uploadAvatar: async function(formData) {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error('用户未登录或token已过期');

      const response = await fetch(`${API_BASE_URL}/user/avatar`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData,
        credentials: 'include'
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error(data.message || '登录已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(`头像上传失败: ${data.message || response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('uploadAvatar API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 更新用户个人信息
   * 对应后端接口：PUT /api/user/info
   * @param {Object} userData 包含用户信息的对象
   * @returns {Promise<Object>} 更新后的用户信息
   */
  updateUserInfo: async function(userData) {
    try {
      const response = await fetch(`${API_BASE_URL}/user/info`, {
        method: 'PUT',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(userData),
        credentials: 'include'
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error(data.message || '登录已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(`更新用户信息失败: ${data.message || response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('updateUserInfo API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 修改用户密码
   * 对应后端接口：POST /api/user/change-password
   * @param {Object} passwordData 包含旧密码和新密码的对象
   * @returns {Promise<Object>} 操作结果
   */
  changePassword: async function(passwordData) {
    try {
      const response = await fetch(`${API_BASE_URL}/user/change-password`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(passwordData),
        credentials: 'include'
      });

      const data = await response.json();

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error(data.message || '登录已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(`修改密码失败: ${data.message || response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('changePassword API调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 医生工作站：获取患者列表
   * 真实接口优先；若后端未提供则回退到本地模拟数据
   * @returns {Promise<Array>} 医生端患者列表
   */
  getDoctorPatients: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/doctor/patients`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `获取患者列表失败: ${response.statusText}`);
      }

      const data = await response.json();
      if (!Array.isArray(data)) throw new Error('患者列表数据格式错误');

      return data.map(normalizeDoctorPatient);
    } catch (error) {
      console.error('getDoctorPatients 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 医生工作站：获取患者报告详情（含影像）
   * 真实接口优先；若后端未提供则从模拟数据返回
   * @param {number|string} patientId 患者ID
   * @returns {Promise<Object>} 报告详情
   */
  getDoctorPatientReport: async function(patientId) {
    try {
      const response = await fetch(`${API_BASE_URL}/doctor/patients/${patientId}/report`, {
        method: 'GET',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (response.status === 401) {
        localStorage.removeItem('access_token');
        throw new Error('登录已过期，请重新登录');
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `获取患者报告失败: ${response.statusText}`);
      }

      const data = await response.json();
      return normalizeDoctorPatient(data || {});
    } catch (error) {
      console.error('getDoctorPatientReport 调用失败:', error.message);
      throw error;
    }
  },

  /**
   * 用户退出登录
   * 对应后端接口：POST /api/logout
   * @returns {Promise<Object>} 退出结果
   */
  logout: async function() {
    try {
      const response = await fetch(`${API_BASE_URL}/logout`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      const data = await response.json();

      // 无论成功与否都清除本地token
      localStorage.removeItem('access_token');

      if (!response.ok) {
        throw new Error(`退出登录失败: ${data.message || response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('logout API调用失败:', error.message);
      throw error;
    }
  }
};