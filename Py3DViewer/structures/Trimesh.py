from .Abstractmesh import AbstractMesh
from ..visualization.Viewer import Viewer
import numpy as np
from ..utils import IO, ObservableArray
from ..utils.metrics import triangle_aspect_ratio, triangle_area

class Trimesh(AbstractMesh):

    """
    This class represent a mesh composed of triangles. It is possible to load the mesh from a file (.obj) or
    from raw geometry and topology data.

    Parameters:

        filename (string): The name of the file to load 
        vertices (Array (Nx3) type=float): The list of vertices of the mesh
        faces (Array (Nx3) type=int): The list of faces of the mesh
        labels (Array (Nx1) type=int): The list of labels of the mesh (Optional)

    
    """
    
    def __init__(self, filename = None, vertices = None, faces = None, labels = None):
        
        self.face_normals     = None #npArray (Nx3)
        self.labels      = None #npArray (Nx1)
        self.__face2face      = None #npArray (Nx3?)
        
        super(Trimesh, self).__init__()
        
        if filename is not None:
            
            self.__load_from_file(filename)
        
        elif vertices and faces:
            
            self.vertices = ObservableArray(vertices.shape)
            self.vertices[:] = vertices
            self.vertices.attach(self)
            self.faces = ObservableArray(faces.shape, dtype=np.int)
            self.faces[:] = faces
            self.faces.attach(self)
            self.__load_operations()
        
            if labels:
                self.labels = ObservableArray(labels.shape)
                self.labels[:] = labels
                self.labels.attach(self)
            
        else:
            print('Warning: Empty Trimesh object')
         
    
    # ==================== METHODS ==================== #    
        
    @property
    def num_faces(self):
        
        return self.faces.shape[0]


    def add_face(self,face_id0, face_id1, face_id2):
        """
        Add a new face to the current mesh. It affects the mesh topology. 

        Parameters:

            face_id0 (int): The index of the first vertex composing the new face
            face_id1 (int): The index of the second vertex composing the new face
            face_id2 (int): The index of the third vertex composing the new face
    
        """
        self.add_faces([face_id0, face_id1, face_id2])
        
        
    def add_faces(self, new_faces):
        
        """
        Add a list of new faces to the current mesh. It affects the mesh topology. 

        Parameters:

            new_faces (Array (Nx3) type=int): List of faces to add. Each face is in the form [int,int,int]
    
        """
            
        new_faces = np.array(new_faces)
        new_faces.shape = (-1,3)
                
        if new_faces[(new_faces[:,0] > self.num_vertices) | 
                     (new_faces[:,1] > self.num_vertices) | 
                     (new_faces[:,2] > self.num_vertices)].shape[0] > self.num_vertices:
            raise Exception('The Id of a vertex must be lesser than the number of vertices')

        self.faces = np.concatenate([self.faces, new_faces])
        self.__load_operations()
        
    
    def remove_face(self,face_id):

        """
        Remove a face from the current mesh. It affects the mesh topology. 

        Parameters:

            face_id (int): The index of the face to remove 
    
        """

        self.remove_faces([face_id])
        
        
    def remove_faces(self, face_ids):

        """
        Remove a list of faces from the current mesh. It affects the mesh topology. 

        Parameters:

            face_ids (Array (Nx1 / 1xN) type=int): List of faces to remove. Each face is in the form [int]
    
        """
        
        face_ids = np.array(face_ids)
        mask = np.ones(self.num_faces)
        mask[face_ids] = 0
        mask = mask.astype(np.bool)
        
        self.faces = self.faces[mask]
        self.__load_operations()
        
    
    def remove_vertex(self,vtx_id):

        """
        Remove a vertex from the current mesh. It affects the mesh geometry. 

        Parameters:

            vtx_id (int): The index of the vertex to remove 
    
        """
        
        self.remove_vertices([vtx_id])
    
    
    def remove_vertices(self, vtx_ids):
        """
        Remove a list of vertices from the current mesh. It affects the mesh geoemtry. 

        Parameters:

            vtx_ids (Array (Nx1 / 1xN) type=int): List of vertices to remove. Each vertex is in the form [int]
    
        """ 
        vtx_ids = np.array(vtx_ids)
        
        for v_id in vtx_ids:
                        
            self.vertices = np.delete(self.vertices, v_id, 0)
            self.faces = self.faces[(self.faces[:,0] != v_id) & 
                                    (self.faces[:,1] != v_id) & 
                                    (self.faces[:,2] != v_id)]
            
            self.faces[(self.faces[:,0] > v_id)] -= np.array([1, 0, 0])
            self.faces[(self.faces[:,1] > v_id)] -= np.array([0, 1, 0])
            self.faces[(self.faces[:,2] > v_id)] -= np.array([0, 0, 1])
            
            vtx_ids[vtx_ids > v_id] -= 1;
            
        self.__load_operations()
        
        
    def __load_operations(self):
        
        self.__compute_adjacencies()
        self._AbstractMesh__update_bounding_box()
        self.reset_clipping()
        self.__compute_face_normals()
        self.__compute_vertex_normals()
        self.__compute_metrics()
    
    
    def __compute_adjacencies(self):
        
        map_ = dict()
        adjs =  np.zeros((self.num_faces, 3))-1
        vtx2vtx = [[] for i in range(self.num_vertices)]
        vtx2face = [[] for i in range(self.num_vertices)]


        edges = np.c_[self.faces[:,0], self.faces[:,1], 
                      self.faces[:,1], self.faces[:,2], 
                      self.faces[:,2], self.faces[:,0]]
        edges.shape = (-1, 2)
        faces_idx = np.repeat(np.array(range(self.num_faces)), 3)
        
        for e, f in zip(edges, faces_idx):
            
            vtx2vtx[e[0]].append(e[1])
            vtx2face[e[0]].append(f)
            vtx2face[e[1]].append(f)
            
            e = (e[0], e[1])

            try:
                tmp = map_[e]
            except KeyError:
                tmp = None

            if tmp is None:
                map_[(e[1], e[0])] = f
            else:
                idx_to_append1 = np.where(adjs[f] == -1)[0][0]
                idx_to_append2 = np.where(adjs[map_[e]] == -1)[0][0]
                adjs[f][idx_to_append1] = map_[e]
                adjs[map_[e]][idx_to_append2] = f
                


        self.__face2face =  adjs
        self._AbstractMesh__vtx2vtx = np.array([np.array(a) for a in vtx2vtx])
        self._AbstractMesh__vtx2face = np.array([np.unique(np.array(a)) for a in vtx2face])

        
    def __compute_face_normals(self):
        
        e1_v = self.vertices[self.faces][:,1] - self.vertices[self.faces][:,0]
        e2_v = self.vertices[self.faces][:,2] - self.vertices[self.faces][:,1]
        
        self.face_normals = np.cross(e1_v, e2_v)
        norm = np.linalg.norm(self.face_normals, axis=1)
        norm.shape = (-1,1)
        self.face_normals = self.face_normals / norm
        
    
    def __compute_vertex_normals(self):
        
        self.vtx_normals = np.array([np.mean(self.face_normals[v2f], axis = 0) for v2f in self.vtx2face])
        norm = np.linalg.norm(self.vtx_normals, axis=1)
        norm.shape = (-1,1)
        self.vtx_normals = self.vtx_normals / norm
        
        
    def __load_from_file(self, filename):
        
        ext = filename.split('.')[-1]
        
        if ext == 'obj':
            self.vertices, self.faces, self.face_normals = IO.read_obj(filename)
            self.vertices.attach(self)
            self.faces.attach(self)
            self.face_normals.attach(self)
            
        else:
            raise Exception("Only .obj files are supported")
            
        self.__load_operations()
        
        return self
        
    
    def save_file(self, filename):

        """
        Save the current mesh in a file. Currently it supports the .obj extension. 

        Parameters:

            filename (string): The name of the file
    
        """
        
        ext = filename.split('.')[-1]
        
        if ext == 'obj':
            IO.save_obj(self, filename)
        
    
    def __compute_metrics(self): 
        
        self.simplex_metrics['area'] = triangle_area(self.vertices, self.faces)
        self.simplex_metrics['aspect_ratio'] = triangle_aspect_ratio(self.vertices, self.faces)
        
    
    def boundary(self):
        
        """
        Compute the boundary of the current mesh. It only returns the faces that are inside the clipping
        """
        if (self._AbstractMesh__boundary_needs_update):
            print("Calculating new boundary")
            clipping_range = super(Trimesh, self).boundary()
            self._AbstractMesh__boundary_cached = clipping_range
            self._AbstractMesh__boundary_needs_update = False
        
        return self.faces[self._AbstractMesh__boundary_cached], self._AbstractMesh__boundary_cached
    
        
    @property
    def face2face(self):
        return self.__face2face

    @property
    def visibleFaces(self):
        return self.boundary[0]
        
    @property
    def simplex_centroids(self):
        
        if self._AbstractMesh__simplex_centroids is None:
            self._AbstractMesh__simplex_centroids = self.vertices[self.faces].mean(axis = 1)
            self._AbstractMesh__simplex_centroids._observers = self.vertices._observers
        return self._AbstractMesh__simplex_centroids
    
    @property
    def edges(self):
        
        edges =  np.c_[self.faces[:,:2], self.faces[:,1:], self.faces[:,2], self.faces[:,0]]
        edges.shape = (-1,2)
        
        return edges
       
    
    