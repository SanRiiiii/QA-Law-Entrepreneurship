from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from app.core.config import settings
import logging

class VectorStore:
    def __init__(self):
        self.collections = {}  # 字典，键为集合名称，值为集合对象
        self.logger = logging.getLogger(__name__)
     
    def connect_to_milvus(self):
        """连接到Milvus向量数据库"""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            self.logger.info("Milvus连接成功")
            return True
        except Exception as e:
            self.logger.error(f"Milvus连接失败: {e}")
            return False

    def check_collection_exists(self, collection_name):
        """检查集合是否存在"""
        return utility.has_collection(collection_name)

    def get_collection(self, collection_name):
        """获取文档集合"""
        if collection_name in self.collections:
            return self.collections[collection_name]
            
        if not self.check_collection_exists(collection_name):
            return None
            
        self.collections[collection_name] = Collection(collection_name)
        return self.collections[collection_name]
    
    def create_collection(self, fields, collection_name, description):
        """
        创建集合
        需要外部传输fields和collection_name和description
        """
        if self.check_collection_exists(collection_name):
            self.logger.info(f"集合 {collection_name} 已存在")
            return self.get_collection(collection_name)
        
        # 创建集合模式
        schema = CollectionSchema(fields, description)
        
        # 创建集合
        collection = Collection(collection_name, schema=schema)
        self.collections[collection_name] = collection
        
        # 创建索引
        index_params = {
            "metric_type": "COSINE",  # 余弦相似度
            "index_type": "HNSW",     # 高效的近似最近邻搜索
            "params": {
                "M": 16,              # HNSW图中每个节点的最大边数
                "efConstruction": 200 # 构建时的搜索宽度
            }
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        
        self.logger.info(f"已成功创建集合 {collection_name} 并设置索引")
        return collection
    
    def insert_vectors(self, collection_name, entities):
        """插入向量数据"""
        collection = self.get_collection(collection_name)
        if not collection:
            self.logger.error(f"集合 {collection_name} 不存在")
            return None
        
        try:
            insert_result = collection.insert(entities)
            collection.flush()
            self.logger.info(f"成功插入 {len(entities)} 条数据到集合 {collection_name}")
            return insert_result
        except Exception as e:
            self.logger.error(f"插入数据失败: {e}")
            return None
    
    def search_vectors(self, collection_name, query_embedding, limit=10, output_fields=None):
        """搜索向量"""
        collection = self.get_collection(collection_name)
        if not collection:
            self.logger.error(f"集合 {collection_name} 不存在")
            return []
        
        # 加载集合
        collection.load()
        
        # 设置默认输出字段
        if output_fields is None:
            output_fields = ["id", "content", "document_name", "chapter", "section"]
        
        # 搜索参数
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 100}  # 搜索时的候选集大小
        }
        
        try:
            results = collection.search(
                data=[query_embedding], 
                anns_field="embedding", 
                param=search_params,
                limit=limit,
                output_fields=output_fields
            )
            
            # 处理结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = {
                        'uuid': hit.id,
                        'score': hit.score,
                    }
                    # 添加其他字段
                    for field in output_fields:
                        if field != "id":  # id已经作为uuid添加
                            result[field] = hit.entity.get(field)
                    
                    search_results.append(result)
            
            return search_results
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
            return []
    
    def delete_vectors(self, collection_name, ids):
        """删除向量"""
        collection = self.get_collection(collection_name)
        if not collection:
            self.logger.error(f"集合 {collection_name} 不存在")
            return False
        
        try:
            expr = f"id in {ids}"
            collection.delete(expr)
            self.logger.info(f"成功删除集合 {collection_name} 中 ID 为 {ids} 的向量")
            return True
        except Exception as e:
            self.logger.error(f"删除向量失败: {e}")
            return False
    
    def drop_collection(self, collection_name):
        """删除集合"""
        if self.check_collection_exists(collection_name):
            utility.drop_collection(collection_name)
            if collection_name in self.collections:
                del self.collections[collection_name]
            self.logger.info(f"已删除集合 {collection_name}")
            return True
        return False
    
    def get_collection_stats(self, collection_name):
        """获取集合统计信息"""
        collection = self.get_collection(collection_name)
        if not collection:
            return {"error": f"集合 {collection_name} 不存在"}
        
        try:
            stats = {
                "name": collection_name,
                "num_entities": collection.num_entities,
                "index_status": "已建立" if collection.has_index() else "未建立"
            }
            return stats
        except Exception as e:
            self.logger.error(f"获取集合统计信息失败: {e}")
            return {"error": str(e)}