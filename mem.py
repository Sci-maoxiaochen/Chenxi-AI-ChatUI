import numpy as np
import faiss
import pickle
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer
from typing import List, Tuple

def get_user_directory():
    user_directory = os.path.expanduser("~")
    return user_directory

class CategoryVectorStore:
    def __init__(self):
        # 初始化模型
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_dimension = 384
        
        # 初始化FAISS索引用于存储分类的向量
        self.category_index = faiss.IndexFlatL2(self.vector_dimension)
        
        # 存储分类到句子的映射
        self.category_to_sentences = {}
        # 存储分类名称列表（与FAISS索引顺序对应）
        self.categories = []

    def add_sentence(self, sentence: str, category: str):
        """添加句子和分类"""
        if category not in self.category_to_sentences:
            # 为新分类生成向量
            category_vector = self.model.encode([category])[0]
            category_vector_np = np.array([category_vector]).astype('float32')
            
            # 将分类向量添加到FAISS
            self.category_index.add(category_vector_np)
            
            # 记录新分类
            self.categories.append(category)
            self.category_to_sentences[category] = []
            
        # 添加句子到对应分类
        self.category_to_sentences[category].append(sentence)

    def search_most_similar_category(self, query: str, k: int = 1) -> List[Tuple[str, List[str]]]:
        """搜索最相似的分类及其下的句子"""
        # 生成查询向量
        query_vector = self.model.encode([query])[0]
        query_vector_np = np.array([query_vector]).astype('float32')
        
        # 使用FAISS搜索最相似的分类
        distances, indices = self.category_index.search(query_vector_np, k)
        
        # 获取结果
        results = []
        for idx in indices[0]:
            if idx < len(self.categories):
                category = self.categories[idx]
                sentences = self.category_to_sentences[category]
                results.append((category, sentences))

        return results

    def save(self, save_dir: str = get_user_directory()):
        """
        保存向量存储到磁盘
        """
        # 创建保存目录
        os.makedirs(save_dir, exist_ok=True)
        
        # 保存FAISS索引
        faiss_path = os.path.join(save_dir, "category_vectors.faiss")
        faiss.write_index(self.category_index, faiss_path)
        
        # 保存其他数据（分类列表和句子映射）
        metadata = {
            'categories': self.categories,
            'category_to_sentences': self.category_to_sentences,
            'save_time': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        metadata_path = os.path.join(save_dir, "metadata.pkl")
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
            
        print(f"数据已保存到目录: {save_dir}")
        print(f"- FAISS索引: {faiss_path}")
        print(f"- 元数据: {metadata_path}")

    @classmethod
    def load(cls, save_dir: str = get_user_directory()) -> 'CategoryVectorStore':
        """
        从磁盘加载向量存储
        """
        if not os.path.exists(save_dir):
            raise FileNotFoundError(f"保存目录不存在: {save_dir}")
            
        # 创建新实例
        store = cls()
        
        # 加载FAISS索引
        faiss_path = os.path.join(save_dir, "category_vectors.faiss")
        store.category_index = faiss.read_index(faiss_path)
        
        # 加载元数据
        metadata_path = os.path.join(save_dir, "metadata.pkl")
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
            
        # 恢复数据
        store.categories = metadata['categories']
        store.category_to_sentences = metadata['category_to_sentences']
        
        print(f"成功加载数据 (保存时间: {metadata['save_time']})")
        return store